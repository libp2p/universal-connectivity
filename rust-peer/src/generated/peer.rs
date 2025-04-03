// Automatically generated rust module for 'peer.proto' file

#![allow(non_snake_case)]
#![allow(non_upper_case_globals)]
#![allow(non_camel_case_types)]
#![allow(unused_imports)]
#![allow(unknown_lints)]
#![allow(clippy::all)]
#![cfg_attr(rustfmt, rustfmt_skip)]


use std::borrow::Cow;
use quick_protobuf::{MessageInfo, MessageRead, MessageWrite, BytesReader, Writer, WriterBackend, Result};
use quick_protobuf::sizeofs::*;
use super::*;

#[allow(clippy::derive_partial_eq_without_eq)]
#[derive(Debug, Default, PartialEq, Clone)]
pub struct Peer<'a> {
    pub publicKey: Cow<'a, [u8]>,
    pub multiAddrs: Vec<Cow<'a, [u8]>>,
}

impl<'a> MessageRead<'a> for Peer<'a> {
    fn from_reader(r: &mut BytesReader, bytes: &'a [u8]) -> Result<Self> {
        let mut msg = Self::default();
        while !r.is_eof() {
            match r.next_tag(bytes) {
                Ok(10) => msg.publicKey = r.read_bytes(bytes).map(Cow::Borrowed)?,
                Ok(18) => msg.multiAddrs.push(r.read_bytes(bytes).map(Cow::Borrowed)?),
                Ok(t) => { r.read_unknown(bytes, t)?; }
                Err(e) => return Err(e),
            }
        }
        Ok(msg)
    }
}

impl<'a> MessageWrite for Peer<'a> {
    fn get_size(&self) -> usize {
        0
        + if self.publicKey == Cow::Borrowed(b"") { 0 } else { 1 + sizeof_len((&self.publicKey).len()) }
        + self.multiAddrs.iter().map(|s| 1 + sizeof_len((s).len())).sum::<usize>()
    }

    fn write_message<W: WriterBackend>(&self, w: &mut Writer<W>) -> Result<()> {
        if self.publicKey != Cow::Borrowed(b"") { w.write_with_tag(10, |w| w.write_bytes(&**&self.publicKey))?; }
        for s in &self.multiAddrs { w.write_with_tag(18, |w| w.write_bytes(&**s))?; }
        Ok(())
    }
}

