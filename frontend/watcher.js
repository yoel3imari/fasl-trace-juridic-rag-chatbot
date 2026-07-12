/* eslint-disable @typescript-eslint/no-require-imports */
const chokidar = require("chokidar");
const { exec } = require("child_process");
const { config } = require("dotenv");

config({ path: ".env.local" });

const openapiFile = process.env.OPENAPI_OUTPUT_FILE;

if (!openapiFile) {
  console.error("OPENAPI_OUTPUT_FILE is not set in .env.local");
  process.exit(1);
}

console.log(`\x1b[36m👁️  Watcher started — monitoring ${openapiFile}\x1b[0m`);

chokidar.watch(openapiFile).on("change", (path) => {
  console.log(
    `\x1b[34mFile ${path} has been modified. Running generate-client...\x1b[0m`
  );
  exec("bun run generate-client", (error, stdout, stderr) => {
    if (error) {
      console.error(`\x1b[31mError: ${error.message}\x1b[0m`);
      return;
    }
    if (stderr) {
      console.error(`\x1b[31mstderr: ${stderr}\x1b[0m`);
      return;
    }
    console.log(`\x1b[32m${stdout}\x1b[0m`);
    console.log("\x1b[32mClient regenerated successfully.\x1b[0m");
  });
});
