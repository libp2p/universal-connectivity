use async_trait::async_trait;
use futures::{io, AsyncRead, AsyncWrite};
use libp2p::{
    core::upgrade::{read_length_prefixed, write_length_prefixed},
    request_response, StreamProtocol,
};

// Simple file exchange protocol

#[derive(Default, Clone)]
pub struct FileExchangeCodec;

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct FileRequest {
    pub file_id: String,
}
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct FileResponse {
    pub file_body: Vec<u8>,
}

#[async_trait]
impl request_response::Codec for FileExchangeCodec {
    type Protocol = StreamProtocol;
    type Request = FileRequest;
    type Response = FileResponse;

    async fn read_request<T>(&mut self, _: &StreamProtocol, io: &mut T) -> io::Result<Self::Request>
    where
        T: AsyncRead + Unpin + Send,
    {
        let vec = read_length_prefixed(io, 1_000_000).await?;

        if vec.is_empty() {
            return Err(io::ErrorKind::UnexpectedEof.into());
        }

        Ok(FileRequest {
            file_id: String::from_utf8(vec).unwrap(),
        })
    }

    async fn read_response<T>(
        &mut self,
        _: &StreamProtocol,
        io: &mut T,
    ) -> io::Result<Self::Response>
    where
        T: AsyncRead + Unpin + Send,
    {
        let vec = read_length_prefixed(io, 500_000_000).await?; // update transfer maximum

        if vec.is_empty() {
            return Err(io::ErrorKind::UnexpectedEof.into());
        }

        Ok(FileResponse { file_body: vec })
    }

    async fn write_request<T>(
        &mut self,
        _: &StreamProtocol,
        io: &mut T,
        FileRequest { file_id }: FileRequest,
    ) -> io::Result<()>
    where
        T: AsyncWrite + Unpin + Send,
    {
        write_length_prefixed(io, file_id).await?;

        Ok(())
    }

    async fn write_response<T>(
        &mut self,
        _: &StreamProtocol,
        io: &mut T,
        FileResponse { file_body }: FileResponse,
    ) -> io::Result<()>
    where
        T: AsyncWrite + Unpin + Send,
    {
        write_length_prefixed(io, file_body).await?;

        Ok(())
    }
}
