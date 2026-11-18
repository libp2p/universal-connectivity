"""Listen/announce address resolution and dial-address normalisation.

The engine still owns the libp2p host, but the policy around which addresses
are bindable, which are advertised, and how operator-supplied dial addresses
are rewritten lives here.
"""

from __future__ import annotations

import errno
import ipaddress
import logging
import socket
from typing import Any, List

import multiaddr

from ..constants import WEBRTC_DIRECT_PORT_OFFSET, WEBTRANSPORT_PORT_OFFSET

logger = logging.getLogger("app.services.addressing")

SUPPORTED_LISTEN_PROTOCOLS = {
    "tcp",
    "udp",
    "ws",
    "wss",
    "quic",
    "quic-v1",
    "webtransport",
    "webrtc",
    "webrtc-direct",
}


def has_webrtc_support() -> bool:
    """Return True if aiortc (the WebRTC-direct backend) is importable."""
    try:
        import aiortc  # noqa: F401

        return True
    except ImportError:
        return False


def default_listen_specs(
    base_port: int, *, include_webrtc_direct: bool = True
) -> list[str]:
    """Build the default multi-transport listener list for *base_port*.

    All five transports are advertised by the DApp, and py-libp2p builds a
    transport from whichever listen multiaddr it sees. WebTransport and
    WebRTC-direct each terminate their own TLS certificate, so they cannot
    share the QUIC-v1 socket and are offset from the base port.

    A *base_port* of 0 means "let the kernel pick": every transport then binds
    its own ephemeral port (offsetting would ask for privileged ports 1 and 2).
    """
    if base_port == 0:
        tcp = quic = webtransport = webrtc = 0
    else:
        tcp = quic = base_port
        webtransport = base_port + WEBTRANSPORT_PORT_OFFSET
        webrtc = base_port + WEBRTC_DIRECT_PORT_OFFSET

    specs = [
        f"/ip4/0.0.0.0/tcp/{tcp}",
        f"/ip4/0.0.0.0/tcp/{tcp}/ws",
        f"/ip4/0.0.0.0/udp/{quic}/quic-v1",
        f"/ip4/0.0.0.0/udp/{webtransport}/quic-v1/webtransport",
    ]
    if include_webrtc_direct:
        specs.append(f"/ip4/0.0.0.0/udp/{webrtc}/webrtc-direct")
    return specs


class AddressService:
    """Resolve, validate, rewrite, and snapshot peer addresses."""

    def __init__(self, engine: Any) -> None:
        self._engine = engine

    # ------------------------------------------------------------------ #
    #  Listen / announce resolution
    # ------------------------------------------------------------------ #
    def resolve_listen_addrs(self) -> List[multiaddr.Multiaddr]:
        """Parse and validate the configured listen addresses.

        Without an explicit ``--listen-addr`` the peer binds every transport the
        DApp advertises: TCP, WebSocket, QUIC-v1, WebTransport and
        WebRTC-direct.
        """
        base_port = self._engine.port
        if self._engine.listen_addrs:
            raw = self._engine.listen_addrs
        else:
            raw = default_listen_specs(
                base_port, include_webrtc_direct=has_webrtc_support()
            )
            if not has_webrtc_support():
                logger.warning(
                    "aiortc is not installed; WebRTC-direct listener disabled. "
                    "Install the aiortc extra to serve browser peers."
                )

        resolved = []
        for item in raw:
            try:
                addr = multiaddr.Multiaddr(item)
            except Exception as exc:
                raise ValueError(f"Invalid listen address {item!r}: {exc}") from exc
            protocols = {p.name for p in addr.protocols()}
            if not (protocols & {"tcp", "udp"}):
                raise ValueError(
                    f"Unsupported listen address {item!r}: expected a TCP or UDP multiaddr"
                )
            unsupported = protocols - SUPPORTED_LISTEN_PROTOCOLS - {"ip4", "ip6", "p2p", "certhash"}
            if unsupported:
                raise ValueError(
                    f"Unsupported listen address {item!r}: protocol "
                    f"{next(iter(unsupported))!r} is not supported"
                )
            resolved.append(addr)
        return resolved

    def resolve_announce_addrs(self) -> List[multiaddr.Multiaddr]:
        """Parse explicit announce addresses and reject undialable wildcards."""
        if not self._engine.announce_addrs:
            return []
        resolved = []
        for item in self._engine.announce_addrs:
            try:
                addr = multiaddr.Multiaddr(item)
            except Exception as exc:
                raise ValueError(f"Invalid announce address {item!r}: {exc}") from exc
            protocols = {p.name for p in addr.protocols()}
            if "ip4" in protocols and addr.value_for_protocol("ip4") == "0.0.0.0":
                raise ValueError(
                    f"Announce address {item!r} uses the wildcard host 0.0.0.0; "
                    "use a concrete dialable IP"
                )
            if "ip6" in protocols and addr.value_for_protocol("ip6") in ("::", "::0"):
                raise ValueError(
                    f"Announce address {item!r} uses the wildcard host ::; "
                    "use a concrete dialable IP"
                )
            resolved.append(addr)
        return resolved

    def make_addrs_factory(self) -> Any:
        """Return an AddrsFactory that never advertises a wildcard address.

        The factory only rewrites wildcard listeners (the socket is bound on
        all interfaces, so a concrete host is valid). A listener explicitly
        bound to a concrete address is advertised as-is; if that address is
        loopback, the caller gets a clear warning rather than a silent rewrite
        that would point at an interface the peer is not listening on.
        """
        if self._engine.announce_addrs:
            return None  # explicit static addresses win
        host = (self._engine.announce_host or "").strip()
        if not host:
            return None
        if host in ("0.0.0.0", "::", "::0"):
            raise ValueError(
                "announce_host cannot be a wildcard address; use a concrete "
                "dialable IP (or an explicit --announce-addr)"
            )
        announce_is_v6 = ":" in host

        def _factory(
            candidates: list[multiaddr.Multiaddr],
        ) -> list[multiaddr.Multiaddr]:
            advertised = []
            seen = set()
            for addr in candidates:
                text = str(addr)
                protocols = {p.name for p in addr.protocols()}
                if "ip4" in protocols:
                    value = addr.value_for_protocol("ip4")
                    if value == "0.0.0.0":
                        if announce_is_v6:
                            continue
                        text = text.replace("/ip4/0.0.0.0/", f"/ip4/{host}/", 1)
                    elif not announce_is_v6 and (
                        "certhash" in protocols
                        or "webtransport" in protocols
                        or "webrtc-direct" in protocols
                    ):
                        # For transports requiring certhashes that bind local interfaces,
                        # also advertise the public announce_host with the bound certhashes.
                        public_text = text.replace(f"/ip4/{value}/", f"/ip4/{host}/", 1)
                        if public_text not in seen:
                            seen.add(public_text)
                            advertised.append(multiaddr.Multiaddr(public_text))
                elif "ip6" in protocols:
                    value = addr.value_for_protocol("ip6")
                    if value in ("::", "::0"):
                        if not announce_is_v6:
                            continue
                        text = text.replace("/ip6/::/", f"/ip6/{host}/", 1)
                if text not in seen:
                    seen.add(text)
                    advertised.append(multiaddr.Multiaddr(text))
            return advertised

        return _factory

    # ------------------------------------------------------------------ #
    #  Port probing and listener verification
    # ------------------------------------------------------------------ #
    def warn_if_port_in_use(
        self, listen_addrs: list[multiaddr.Multiaddr]
    ) -> None:
        """Warn when a listen port is already taken by another process."""
        probed = set()
        for addr in listen_addrs:
            protocols = {p.name for p in addr.protocols()}
            if "ip4" not in protocols:
                continue
            host = addr.value_for_protocol("ip4")
            port = None
            sock_type = socket.SOCK_STREAM
            proto_name = "tcp"
            if "tcp" in protocols:
                port = int(addr.value_for_protocol("tcp"))
                sock_type = socket.SOCK_STREAM
                proto_name = "tcp"
            elif "udp" in protocols:
                port = int(addr.value_for_protocol("udp"))
                sock_type = socket.SOCK_DGRAM
                proto_name = "udp"
            else:
                continue
            if port == 0:
                continue
            bind_host = "0.0.0.0" if host == "0.0.0.0" else host
            if (bind_host, proto_name, port) in probed:
                continue
            probed.add((bind_host, proto_name, port))

            probe = socket.socket(socket.AF_INET, sock_type)
            try:
                probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                probe.bind((bind_host, port))
            except OSError as exc:
                if exc.errno == errno.EADDRINUSE:
                    logger.warning(
                        "⚠️  Port %s/%s on %s is already in use by another process. "
                        "Start each local peer with distinct ports.",
                        port,
                        proto_name,
                        bind_host,
                    )
                elif exc.errno == errno.EADDRNOTAVAIL:
                    logger.warning(
                        "Listen host %s:%s is not assigned to this machine; the "
                        "listener will fail to start.",
                        bind_host,
                        port,
                    )
                else:
                    logger.warning(
                        "Could not probe listen address %s:%s: %s",
                        bind_host,
                        port,
                        exc,
                    )
            finally:
                probe.close()

    @staticmethod
    def addr_match_key(
        addr: multiaddr.Multiaddr,
    ) -> tuple[str | None, str | None, str | None, int | None]:
        """Normalize a multiaddr for listener comparison."""
        protocols = {p.name for p in addr.protocols()}
        family = (
            "ip4" if "ip4" in protocols else "ip6" if "ip6" in protocols else None
        )
        host = addr.value_for_protocol(family) if family else None
        transport_proto = (
            "webrtc-direct"
            if "webrtc-direct" in protocols
            else "webtransport"
            if "webtransport" in protocols
            else "quic-v1"
            if "quic-v1" in protocols
            else "quic"
            if "quic" in protocols
            else "ws"
            if "ws" in protocols
            else "wss"
            if "wss" in protocols
            else "tcp"
            if "tcp" in protocols
            else "udp"
            if "udp" in protocols
            else None
        )
        port = None
        for proto in ("tcp", "udp"):
            if proto in protocols:
                port = int(addr.value_for_protocol(proto))
                break
        return (family, host, transport_proto, None if port == 0 else port)

    def verify_listeners(
        self, host: Any, requested: list[multiaddr.Multiaddr]
    ) -> None:
        """Verify that every requested listener actually bound."""
        bound = [str(addr) for addr in host.get_transport_addrs()]
        self._engine.transport_addrs = bound
        if not bound:
            raise RuntimeError("libp2p host did not start any listener")
        bound_keys = [self.addr_match_key(multiaddr.Multiaddr(item)) for item in bound]
        missing = []
        for req in requested:
            family, hostname, proto, port = self.addr_match_key(req)
            is_wildcard = hostname in ("0.0.0.0", "::")
            is_special = proto in ("webtransport", "webrtc-direct")
            matched = any(
                b_family == family
                and b_proto == proto
                and (b_host == hostname or (is_wildcard and is_special))
                and (port is None or b_port == port)
                for b_family, b_host, b_proto, b_port in bound_keys
            )
            if not matched:
                missing.append(str(req))
        if missing:
            raise RuntimeError(
                "libp2p failed to start listener(s): " + ", ".join(missing)
            )
        logger.info("Listener(s) active: %s", ", ".join(bound))

    # ------------------------------------------------------------------ #
    #  Advertisement
    # ------------------------------------------------------------------ #
    @staticmethod
    def is_wildcard_addr(addr: multiaddr.Multiaddr) -> bool:
        """True when a multiaddr binds a wildcard host (0.0.0.0 / ::)."""
        protocols = {p.name for p in addr.protocols()}
        if "ip4" in protocols:
            return addr.value_for_protocol("ip4") == "0.0.0.0"
        if "ip6" in protocols:
            return addr.value_for_protocol("ip6") in ("::", "::0")
        return False

    @staticmethod
    def classify_announced_addr(addr_str: str) -> str:
        """Describe address reachability without claiming it was tested."""
        try:
            addr = multiaddr.Multiaddr(addr_str)
            protocols = {p.name for p in addr.protocols()}
            if "ip4" in protocols:
                ip = ipaddress.ip_address(addr.value_for_protocol("ip4"))
            elif "ip6" in protocols:
                ip = ipaddress.ip_address(addr.value_for_protocol("ip6"))
            else:
                return "non-IP"
        except Exception:
            return "unparsed"
        if ip.is_unspecified:
            return "wildcard (not dialable)"
        if ip.is_loopback:
            return "loopback (same-machine only)"
        if ip.is_link_local:
            return "link-local (same link only)"
        if ip.is_private:
            return "private/LAN (reachable only on that network)"
        return "public/unknown (reachability not verified)"

    def refresh_advertised_addrs(self, host: Any) -> None:
        """Snapshot and log host.get_addrs() after listeners are ready."""
        advertised = [str(addr) for addr in host.get_addrs()]
        self._engine.full_multiaddrs = advertised
        self._engine.full_multiaddr = advertised[0] if advertised else None
        if not advertised:
            logger.warning(
                "No advertised addresses: this peer can dial out, but has no "
                "address to share. Check --listen-addr / --announce-host / "
                "--announce-addr (the address family must match)."
            )
            return
        for addr in advertised:
            category = self.classify_announced_addr(addr)
            logger.info("Advertised address [%s]: %s", category, addr)
            if category.startswith("loopback"):
                logger.warning(
                    "Advertising a loopback address: only peers on this machine "
                    "can dial it. Use --announce-host <LAN IP> or "
                    "--announce-addr <multiaddr> for other peers."
                )

    # ------------------------------------------------------------------ #
    #  Dial addresses
    # ------------------------------------------------------------------ #
    @staticmethod
    def normalize_dial_addr(multiaddr_str: str) -> str:
        """Rewrite wildcard hosts to loopback so pasted addresses are dialable.

        Peers advertise their listen address as /ip4/0.0.0.0/... in older
        versions; 0.0.0.0 only makes sense for binding, never for dialing.
        """
        normalized = multiaddr_str
        if "/ip4/0.0.0.0/" in normalized:
            normalized = normalized.replace("/ip4/0.0.0.0/", "/ip4/127.0.0.1/")
        if "/ip6/::/" in normalized:
            normalized = normalized.replace("/ip6/::/", "/ip6/::1/")
        if normalized != multiaddr_str:
            logger.warning(
                "Dial address contains a wildcard host; using loopback instead: "
                "%s -> %s",
                multiaddr_str,
                normalized,
            )
        return normalized
