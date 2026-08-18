require("dotenv").config();
const app = require("./app");
const runMigrations = require("./db/migrate");

const PORT = process.env.PORT || 3000;

async function start() {
  try {
    await runMigrations();
  } catch (err) {
    console.error("Migrations failed, refusing to start:", err.message);
    process.exit(1);
  }

  app.listen(PORT, () => {
    console.log(`🚀 Server running on port ${PORT}`);
  });
}

start();