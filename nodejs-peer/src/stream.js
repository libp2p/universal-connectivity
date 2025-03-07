/* eslint-disable no-console */
import * as lp from 'it-length-prefixed'
import map from 'it-map'
import { pipe } from 'it-pipe'
import { fromString as uint8ArrayFromString } from 'uint8arrays/from-string'
import { toString as uint8ArrayToString } from 'uint8arrays/to-string'

// Helper: Reads data from stdin and writes to a stream with length-prefixed encoding.
export function stdinToStream(stream) {
    process.stdin.setEncoding('utf8');
    pipe(
      process.stdin,
      (source) => map(source, (string) => uint8ArrayFromString(string + '\n')),
      (source) => lp.encode(source),
      stream.sink
    ).catch(err => {
      console.log('Error in stdinToStream:', err.message);
    });
  }
  
  // Helper: Reads length-prefixed data from a stream and outputs it to the console.
  export function streamToConsole(stream) {
    pipe(
      stream.source,
      (source) => lp.decode(source),
      (source) => map(source, (buf) => uint8ArrayToString(buf.subarray())),
      async function (source) {
        for await (const msg of source) {
          console.log('> ' + msg.toString().trim());
        }
      }
    ).catch(err => {
      console.log('Error in streamToConsole:', err.message);
    });
  }
