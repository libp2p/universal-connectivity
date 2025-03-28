from setuptools import setup, find_packages

setup(
    name="py-peer",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "trio",
        "multiaddr",
        "base58",
        "py-libp2p",
    ],
    entry_points={
        "console_scripts": [
            "py-peer=py_peer.main:main",
        ],
    },
    description="A modular libp2p peer implementation in Python",
    author="Your Name",
    author_email="your.email@example.com",
    url="https://github.com/yourusername/py-peer",
)