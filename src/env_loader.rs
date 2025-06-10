use dotenvy::dotenv;

/// Load environment variables from a .env file.
pub fn load_env() {
    // Load .env file, ignore errors if file not found.
    dotenv().ok();
}
