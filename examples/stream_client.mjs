// Read the NDJSON user stream line by line as it arrives (Node.js 18+, no dependencies).
//
// Start the server first:
//
//     uv run python -m uvicorn config.asgi:application --reload --lifespan off
//
// Then run:
//
//     node examples/stream_client.mjs           // all users
//     node examples/stream_client.mjs Tampa     // only users from Tampa
//     STREAM_URL=http://127.0.0.1:8011/api/users/stream/ node examples/stream_client.mjs
//
// Lines arrive one by one only under ASGI (uvicorn). Under WSGI (manage.py runserver)
// Django buffers the whole stream first, so every line arrives at once at the end.

const url = new URL(process.env.STREAM_URL ?? "http://127.0.0.1:8000/api/users/stream/");
if (process.argv[2]) url.searchParams.set("city", process.argv[2]);

const started = performance.now();
const elapsed = () => ((performance.now() - started) / 1000).toFixed(2).padStart(6);

let response;
try {
  response = await fetch(url);
} catch {
  console.error(`Cannot connect to ${url}: is the server running?`);
  process.exit(1);
}
if (!response.ok) {
  console.error(`HTTP ${response.status}`);
  process.exit(1);
}
console.log(`${response.status} ${response.headers.get("content-type")}`);

let count = 0;
function handle(line) {
  if (!line) return;
  const user = JSON.parse(line); // every line is a complete JSON object
  count += 1;
  console.log(
    `${elapsed()}s  #${String(user.id).padEnd(3)} ${user.username.padEnd(10)} ${user.profile.city}`,
  );
}

// Network chunks do not follow line boundaries: one JSON object can arrive in two
// chunks, so keep the unfinished tail in a buffer until its "\n" arrives.
let buffer = "";
for await (const chunk of response.body.pipeThrough(new TextDecoderStream())) {
  buffer += chunk;
  const lines = buffer.split("\n");
  buffer = lines.pop(); // the last piece has no "\n" yet
  lines.forEach(handle);
}
handle(buffer); // in case the stream did not end with "\n"

console.log(`Done: ${count} users in ${elapsed().trim()}s`);
