//! ECDSA, ECDH (P-256), and AES-GCM via OpenSSL
#![allow(dead_code)]

use anyhow::Result;
use base64::Engine;
use base64::engine::general_purpose::STANDARD;
use hex;
use openssl::derive::Deriver;
use openssl::{
    bn::BigNumContext,
    ec::{EcGroup, EcKey, EcPoint, PointConversionForm},
    nid::Nid,
    pkey::PKey,
    rand::rand_bytes,
    sha::sha256,
    sign::{Signer, Verifier},
    symm::{Cipher, Crypter, Mode},
};
use serde::{Deserialize, Serialize};

/// Encrypted payload format for ECDH + AES-GCM
#[derive(Serialize, Deserialize, Debug)]
pub struct Encrypted {
    pub ephemeral_pk: String,
    pub salt: String,
    pub iv: String,
    pub ciphertext: String,
    pub tag: String,
}

/// Crypto utilities: ECDSA, ECDH, AES-GCM via OpenSSL
#[derive(Clone, Copy)]
pub struct Crypto;

impl Crypto {
    /// Generate ECDSA (P-256) keypair
    pub fn generate_keypair() -> Result<(Vec<u8>, Vec<u8>)> {
        let group = EcGroup::from_curve_name(Nid::X9_62_PRIME256V1)?;
        let key = EcKey::generate(&group)?;
        let private_pem = key.private_key_to_pem()?;
        let public_pem = key.public_key_to_pem()?;
        Ok((private_pem, public_pem))
    }

    /// Sign a message using ECDSA
    pub fn sign(private_pem: &[u8], message: &[u8]) -> Result<Vec<u8>> {
        let key = EcKey::private_key_from_pem(private_pem)?;
        let pkey = PKey::from_ec_key(key)?;
        let mut signer = Signer::new_without_digest(&pkey)?;
        signer.update(message)?;
        Ok(signer.sign_to_vec()?)
    }

    /// Verify an ECDSA signature
    pub fn verify(public_pem: &[u8], message: &[u8], signature: &[u8]) -> bool {
        if let Ok(key) = EcKey::public_key_from_pem(public_pem) {
            if let Ok(pkey) = PKey::from_ec_key(key) {
                if let Ok(mut verifier) = Verifier::new_without_digest(&pkey) {
                    if verifier.update(message).is_ok() {
                        return verifier.verify(signature).unwrap_or(false);
                    }
                }
            }
        }
        false
    }

    /// Encrypt message using ECDH-derived key + AES-256-GCM
    pub fn encrypt(recipient_public_pem: &[u8], plaintext: &[u8]) -> Result<Encrypted> {
        let group = EcGroup::from_curve_name(Nid::X9_62_PRIME256V1)?;
        let recipient_key = EcKey::public_key_from_pem(recipient_public_pem)?;

        // Generate ephemeral key pair
        let eph_key = EcKey::generate(&group)?;
        let mut bn_ctx = BigNumContext::new()?;
        let eph_public_bytes = eph_key.public_key().to_bytes(
            &group,
            PointConversionForm::UNCOMPRESSED,
            &mut bn_ctx,
        )?;
        let eph_pkey = PKey::from_ec_key(eph_key.clone())?;

        // ECDH shared secret
        let recipient_pkey = PKey::from_ec_key(recipient_key)?;
        // ECDH shared secret using OpenSSL Deriver
        let mut deriver = Deriver::new(&eph_pkey)?;
        deriver.set_peer(&recipient_pkey)?;
        let shared_secret = deriver.derive_to_vec()?;

        // Salt + simple HKDF-like derivation via SHA256(salt || shared_secret)
        let mut salt = [0u8; 16];
        rand_bytes(&mut salt)?;
        let derived_key = sha256(&[&salt[..], &shared_secret[..]].concat());

        // AES-GCM encryption
        let mut iv = [0u8; 12];
        rand_bytes(&mut iv)?;

        let mut crypter = Crypter::new(
            Cipher::aes_256_gcm(),
            Mode::Encrypt,
            &derived_key,
            Some(&iv),
        )?;
        let mut ciphertext = vec![0; plaintext.len() + 16];
        let mut count = crypter.update(plaintext, &mut ciphertext)?;
        count += crypter.finalize(&mut ciphertext[count..])?;
        ciphertext.truncate(count);

        let mut tag = [0u8; 16];
        crypter.get_tag(&mut tag)?;

        Ok(Encrypted {
            ephemeral_pk: STANDARD.encode(&eph_public_bytes),
            salt: hex::encode(salt),
            iv: hex::encode(iv),
            ciphertext: hex::encode(ciphertext),
            tag: hex::encode(tag),
        })
    }

    /// Decrypt using private key and AES-GCM
    pub fn decrypt(private_pem: &[u8], enc: &Encrypted) -> Result<Vec<u8>> {
        let group = EcGroup::from_curve_name(Nid::X9_62_PRIME256V1)?;
        let private_key = EcKey::private_key_from_pem(private_pem)?;
        let eph_pub_bytes = STANDARD.decode(&enc.ephemeral_pk)?;
        let mut bn_ctx = BigNumContext::new()?;
        let eph_point = EcPoint::from_bytes(&group, &eph_pub_bytes, &mut bn_ctx)?;
        let eph_key = EcKey::from_public_key(&group, &eph_point)?;
        let eph_pkey = PKey::from_ec_key(eph_key)?;
        let my_pkey = PKey::from_ec_key(private_key)?;

        // Derive shared secret using OpenSSL Deriver
        let mut deriver = Deriver::new(&my_pkey)?;
        deriver.set_peer(&eph_pkey)?;
        let shared_secret = deriver.derive_to_vec()?;
        let salt = hex::decode(&enc.salt)?;
        let derived_key = sha256(&[&salt[..], &shared_secret[..]].concat());

        let iv = hex::decode(&enc.iv)?;
        let ciphertext = hex::decode(&enc.ciphertext)?;
        let tag = hex::decode(&enc.tag)?;

        let mut crypter = Crypter::new(
            Cipher::aes_256_gcm(),
            Mode::Decrypt,
            &derived_key,
            Some(&iv),
        )?;
        crypter.set_tag(&tag)?;

        let mut out = vec![0; ciphertext.len() + 16];
        let mut count = crypter.update(&ciphertext, &mut out)?;
        count += crypter.finalize(&mut out[count..])?;
        out.truncate(count);
        Ok(out)
    }
}
