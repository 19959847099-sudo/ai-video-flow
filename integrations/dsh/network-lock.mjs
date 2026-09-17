// Runtime-only lock; installation uses the normal package manager separately.
import net from 'node:net';
import http from 'node:http';
import https from 'node:https';
import { syncBuiltinESMExports } from 'node:module';
import { writeFileSync } from 'node:fs';

const attempts = [];
function deny() {
  attempts.push({ at: new Date().toISOString(), status: 'blocked' });
  throw new Error('A-04 DSH runtime forbids network requests');
}
net.Socket.prototype.connect = deny;
http.request = deny; http.get = deny;
https.request = deny; https.get = deny;
globalThis.fetch = deny;
syncBuiltinESMExports();
process.on('exit', () => {
  if (process.env.AIGC_NETWORK_AUDIT) writeFileSync(process.env.AIGC_NETWORK_AUDIT,
    JSON.stringify({ network_attempts: attempts, video_api_calls: 0, model_api_calls: 0 }, null, 2));
});
