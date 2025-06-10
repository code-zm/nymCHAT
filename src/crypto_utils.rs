use anyhow::Result;
use base64::{engine::general_purpose, Engine as _};
use hex;
use openssl::ec::{EcGroup, EcKey};
use openssl::hash::MessageDigest;
use openssl::nid::Nid;
use openssl::pkcs5::pbkdf2_hmac;
use openssl::pkey::PKey;
use openssl::rand::rand_bytes;
use openssl::sign::{Signer, Verifier};
use openssl::symm::{Cipher, Crypter, Mode};
use std::fs;
use std::path::PathBuf;

/// Utility for key generation, encryption, signing, and verification.
pub struct CryptoUtils {
    key_dir: PathBuf,
    password: String,
}

impl CryptoUtils {
    /// Create a new CryptoUtils, ensuring the key directory exists.
    pub fn new(key_dir: PathBuf, password: String) -> Result<Self> {
        if !key_dir.exists() {
            fs::create_dir_all(&key_dir)?;
        }
        Ok(Self { key_dir, password })
    }

    fn derive_key(&self, salt: &[u8]) -> Result<[u8; 32]> {
        let mut key = [0u8; 32];
        pbkdf2_hmac(
            self.password.as_bytes(),
            salt,
            100_000,
            MessageDigest::sha256(),
            &mut key,
        )?;
        Ok(key)
    }

    fn encrypt_private_key(&self, private_key_pem: &[u8]) -> Result<String> {
        let mut salt = [0u8; 16];
        rand_bytes(&mut salt)?;
        let mut iv = [0u8; 12];
        rand_bytes(&mut iv)?;
        let key = self.derive_key(&salt)?;
        let cipher = Cipher::aes_256_gcm();
        let mut crypter = Crypter::new(cipher, Mode::Encrypt, &key, Some(&iv))?;
        let mut ciphertext = vec![0; private_key_pem.len() + cipher.block_size()];
        let mut count = crypter.update(private_key_pem, &mut ciphertext)?;
        count += crypter.finalize(&mut ciphertext[count..])?;
        ciphertext.truncate(count);
        let mut tag = [0u8; 16];
        crypter.get_tag(&mut tag)?;
        let mut data = Vec::new();
        data.extend_from_slice(&salt);
        data.extend_from_slice(&iv);
        data.extend_from_slice(&tag);
        data.extend_from_slice(&ciphertext);
        Ok(general_purpose::STANDARD.encode(data))
    }

    fn decrypt_private_key(&self, encrypted_data: &str) -> Result<Vec<u8>> {
        let data = general_purpose::STANDARD.decode(encrypted_data)?;
        let (salt, rest) = data.split_at(16);
        let (iv, rest) = rest.split_at(12);
        let (tag, ciphertext) = rest.split_at(16);
        let key = self.derive_key(salt)?;
        let cipher = Cipher::aes_256_gcm();
        let mut crypter = Crypter::new(cipher, Mode::Decrypt, &key, Some(iv))?;
        crypter.set_tag(tag)?;
        let mut plaintext = vec![0; ciphertext.len() + cipher.block_size()];
        let mut count = crypter.update(ciphertext, &mut plaintext)?;
        count += crypter.finalize(&mut plaintext[count..])?;
        plaintext.truncate(count);
        Ok(plaintext)
    }

    /// Generate and securely store a new ECDSA (P-256) key pair.
    /// Returns the public key PEM as a String.
    pub fn generate_key_pair(&self, username: &str) -> Result<String> {
        let group = EcGroup::from_curve_name(Nid::X9_62_PRIME256V1)?;
        let key = EcKey::generate(&group)?;
        let private_key_pem = key.private_key_to_pem()?;
        let public_key_pem = key.public_key_to_pem()?;
        let encrypted = self.encrypt_private_key(&private_key_pem)?;
        let priv_path = self.key_dir.join(format!("{}_private_key.enc", username));
        let pub_path = self.key_dir.join(format!("{}_public_key.pem", username));
        fs::write(priv_path, encrypted)?;
        fs::write(pub_path, &public_key_pem)?;
        log::info!("generateKeyPair - success!");
        Ok(String::from_utf8(public_key_pem)?)
    }

    /// Load and decrypt a private key for the given username.
    pub fn load_private_key(&self, username: &str) -> Result<PKey<openssl::pkey::Private>> {
        let path = self.key_dir.join(format!("{}_private_key.enc", username));
        let encrypted = fs::read_to_string(path)?;
        let decrypted = self.decrypt_private_key(&encrypted)?;
        let key = EcKey::private_key_from_pem(&decrypted)?;
        Ok(PKey::from_ec_key(key)?)
    }

    /// Load the public key for the given username.
    pub fn load_public_key(&self, username: &str) -> Result<PKey<openssl::pkey::Public>> {
        let path = self.key_dir.join(format!("{}_public_key.pem", username));
        let pem = fs::read(&path)?;
        let key = EcKey::public_key_from_pem(&pem)?;
        Ok(PKey::from_ec_key(key)?)
    }

    /// Sign a message using the user's private key. Returns a hex-encoded signature.
    pub fn sign_message(&self, username: &str, message: &str) -> Result<String> {
        let pkey = self.load_private_key(username)?;
        let mut signer = Signer::new_without_digest(&pkey)?;
        signer.update(message.as_bytes())?;
        let sig = signer.sign_to_vec()?;
        Ok(hex::encode(sig))
    }

    /// Verify a hex-encoded signature against a public key PEM.
    pub fn verify_signature(
        &self,
        public_key_pem: &str,
        message: &str,
        signature_hex: &str,
    ) -> bool {
        if let Ok(sig) = hex::decode(signature_hex) {
            if let Ok(key) = EcKey::public_key_from_pem(public_key_pem.as_bytes()) {
                if let Ok(pkey) = PKey::from_ec_key(key) {
                    if let Ok(mut verifier) = Verifier::new_without_digest(&pkey) {
                        if verifier.update(message.as_bytes()).is_ok() {
                            return verifier.verify(&sig).unwrap_or(false);
                        }
                    }
                }
            }
        }
        log::error!("verifySignature - failed for message signing verification");
        false
    }
}