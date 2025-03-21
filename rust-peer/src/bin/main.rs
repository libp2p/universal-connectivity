use rust_libp2p_webrtc_peer::prelude::*;

use anyhow::Result;
use libp2p::identity;
use libp2p_webrtc::tokio::Certificate;
use std::path::Path;
use tokio::{fs, task::JoinHandle};
use tokio_util::sync::CancellationToken;
use tracing::info;

const LOCAL_KEY_PATH: &str = "./local_key";
const LOCAL_CERT_PATH: &str = "./cert.pem";

#[tokio::main]
async fn main() -> Result<()> {
    // initialize the tracing logger and get the receiver for log messages
    let from_log = Log::init();

    // create a shutdown token
    let shutdown = CancellationToken::new();

    // load the identity and certificate
    let local_key = read_or_create_identity(Path::new(LOCAL_KEY_PATH)).await?;
    let webrtc_cert = read_or_create_certificate(Path::new(LOCAL_CERT_PATH)).await?;

    // create the ui and the channels to communicate with it
    let (mut ui, to_ui, from_ui) = Ui::new(local_key.public().into(), from_log, shutdown.clone());

    // create the peer, connecting it to the ui
    let mut peer = Peer::new(local_key, webrtc_cert, to_ui, from_ui, shutdown.clone()).await?;

    // spawn tasks for both the swarm and the ui
    let peer_task: JoinHandle<Result<()>> = tokio::spawn(async move { peer.run().await });
    let ui_task: JoinHandle<Result<()>> = tokio::spawn(async move { ui.run().await });

    // wait for the tasks to finish
    let (ui_result, peer_result) = tokio::try_join!(peer_task, ui_task)?;

    // check the inner results
    ui_result?;
    peer_result?;

    Ok(())
}

async fn read_or_create_certificate(path: &Path) -> Result<Certificate> {
    if path.exists() {
        let pem = fs::read_to_string(&path).await?;

        info!("Using existing certificate from {}", path.display());

        return Ok(Certificate::from_pem(&pem)?);
    }

    let cert = Certificate::generate(&mut rand::thread_rng())?;
    fs::write(&path, &cert.serialize_pem().as_bytes()).await?;

    info!(
        "Generated new certificate and wrote it to {}",
        path.display()
    );

    Ok(cert)
}

async fn read_or_create_identity(path: &Path) -> Result<identity::Keypair> {
    if path.exists() {
        let bytes = fs::read(&path).await?;

        info!("Using existing identity from {}", path.display());

        return Ok(identity::Keypair::from_protobuf_encoding(&bytes)?); // This only works for ed25519 but that is what we are using.
    }

    let identity = identity::Keypair::generate_ed25519();

    fs::write(&path, &identity.to_protobuf_encoding()?).await?;

    info!("Generated new identity and wrote it to {}", path.display());

    Ok(identity)
}
