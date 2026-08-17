#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KuGou encrypted-audio decryptor (self-contained, standard-library only for KGM/KGMA/VPR).

This module is part of the `kugou-audio-unlock` skill. It does NOT depend on, import from,
or call any external desktop application. It is a standalone, auditable implementation.

Supported input formats:
  * .kgm  / .kgma  / .vpr   -> decrypted with a pure-Python XOR mask (no external files needed)
  * .kgg                 -> requires the user's local KuGou `KGMusicV3.db` (SQLCipher) and
                            `pysqlcipher3`; output is magic-validated so it can never silently
                            corrupt a file. If the DB / key is unavailable, the file is skipped
                            with a clear message.

Output: the *raw* original audio stream (FLAC / MP3 / WAV / OGG), detected from its magic bytes.
The calling skill is responsible for transcoding to MP3 with ffmpeg when needed.

Algorithm reference (KGM/KGMA/VPR): the well-known KGM V2 XOR scheme.
  fileKey      = header[0x1c:0x2c] + 0x00            (17 bytes)
  headerLen    = uint32 LE at header[0x10]
  audio        = bytes of the file starting at headerLen
  out[i]       = T( maskV2(i) ^ audio[i] ^ fileKey[i % 17] )
  T(x)         = x ^ ((x & 0x0f) << 4)
  maskV2(i)    = tableV2[i % 272] ^ maskV1(i >> 4)
  maskV1(o):   while o >= 0x11:  v ^= table1[o % 272]; o >>= 4; v ^= table2[o % 272]; o >>= 4
  (.vpr adds:  out[i] ^= vprKey[i % 17])
"""

import struct
import sys
import os

# ---------------------------------------------------------------------------
# KGM V2 mask tables (verified constants, equivalent to unlock-music / kugou-crypto)
# ---------------------------------------------------------------------------
TABLE_SIZE = 272

table1 = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 33, 1, 97, 1, 33, 1, 225, 1, 33, 1, 97, 1, 33, 1, 210, 35, 2, 2, 66, 66, 2, 2, 194, 194, 2, 2, 66, 66, 2, 2, 211, 211, 2, 3, 99, 67, 99, 3, 227, 195, 227, 3, 99, 67, 99, 3, 148, 180, 148, 101, 4, 4, 4, 4, 132, 132, 132, 132, 4, 4, 4, 4, 149, 149, 149, 149, 4, 5, 37, 5, 229, 133, 165, 133, 229, 5, 37, 5, 214, 182, 150, 182, 214, 39, 6, 6, 198, 198, 134, 134, 198, 198, 6, 6, 215, 215, 151, 151, 215, 215, 6, 7, 231, 199, 231, 135, 231, 199, 231, 7, 24, 56, 24, 120, 24, 56, 24, 233, 8, 8, 8, 8, 8, 8, 8, 8, 25, 25, 25, 25, 25, 25, 25, 25, 8, 9, 41, 9, 105, 9, 41, 9, 218, 58, 26, 58, 90, 58, 26, 58, 218, 43, 10, 10, 74, 74, 10, 10, 219, 219, 27, 27, 91, 91, 27, 27, 219, 219, 10, 11, 107, 75, 107, 11, 156, 188, 156, 124, 28, 60, 28, 124, 156, 188, 156, 109, 12, 12, 12, 12, 157, 157, 157, 157, 29, 29, 29, 29, 157, 157, 157, 157, 12, 13, 45, 13, 222, 190, 158, 190, 222, 62, 30, 62, 222, 190, 158, 190, 222, 47, 14, 14, 223, 223, 159, 159, 223, 223, 31, 31, 223, 223, 159, 159, 223, 223, 14, 15, 0, 32, 0, 96, 0, 32, 0, 224, 0, 32, 0, 96, 0, 32, 0, 241]
table2 = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 35, 1, 103, 1, 35, 1, 239, 1, 35, 1, 103, 1, 35, 1, 223, 33, 2, 2, 70, 70, 2, 2, 206, 206, 2, 2, 70, 70, 2, 2, 222, 222, 2, 3, 101, 71, 101, 3, 237, 207, 237, 3, 101, 71, 101, 3, 157, 191, 157, 99, 4, 4, 4, 4, 140, 140, 140, 140, 4, 4, 4, 4, 156, 156, 156, 156, 4, 5, 39, 5, 235, 141, 175, 141, 235, 5, 39, 5, 219, 189, 159, 189, 219, 37, 6, 6, 202, 202, 142, 142, 202, 202, 6, 6, 218, 218, 158, 158, 218, 218, 6, 7, 233, 203, 233, 143, 233, 203, 233, 7, 25, 59, 25, 127, 25, 59, 25, 231, 8, 8, 8, 8, 8, 8, 8, 8, 24, 24, 24, 24, 24, 24, 24, 24, 8, 9, 43, 9, 111, 9, 43, 9, 215, 57, 27, 57, 95, 57, 27, 57, 215, 41, 10, 10, 78, 78, 10, 10, 214, 214, 26, 26, 94, 94, 26, 26, 214, 214, 10, 11, 109, 79, 109, 11, 149, 183, 149, 123, 29, 63, 29, 123, 149, 183, 149, 107, 12, 12, 12, 12, 148, 148, 148, 148, 28, 28, 28, 28, 148, 148, 148, 148, 12, 13, 47, 13, 211, 181, 151, 181, 211, 61, 31, 61, 211, 181, 151, 181, 211, 45, 14, 14, 210, 210, 150, 150, 210, 210, 30, 30, 210, 210, 150, 150, 210, 210, 14, 15, 0, 34, 0, 102, 0, 34, 0, 238, 0, 34, 0, 102, 0, 34, 0, 254]
tableV2 = [184, 213, 61, 178, 233, 175, 120, 140, 131, 51, 113, 81, 118, 160, 205, 55, 47, 62, 53, 141, 169, 190, 152, 183, 231, 140, 34, 206, 90, 97, 223, 104, 105, 137, 254, 165, 182, 222, 169, 119, 252, 200, 189, 189, 229, 109, 62, 90, 54, 239, 105, 78, 190, 225, 233, 102, 28, 243, 217, 2, 182, 242, 18, 155, 68, 208, 111, 185, 53, 137, 182, 70, 109, 115, 130, 6, 105, 193, 237, 215, 133, 194, 48, 223, 162, 98, 190, 121, 45, 98, 98, 61, 13, 126, 190, 72, 137, 35, 2, 160, 228, 213, 117, 81, 50, 2, 83, 253, 22, 58, 33, 59, 22, 15, 195, 178, 187, 179, 226, 186, 58, 61, 19, 236, 246, 1, 69, 132, 165, 112, 15, 147, 73, 12, 100, 205, 49, 213, 204, 76, 7, 1, 158, 0, 26, 35, 144, 191, 136, 30, 59, 171, 166, 62, 196, 115, 71, 16, 126, 59, 94, 188, 227, 0, 132, 255, 9, 212, 224, 137, 15, 91, 88, 112, 79, 251, 101, 216, 92, 83, 27, 211, 200, 198, 191, 239, 152, 176, 80, 79, 15, 234, 229, 131, 88, 140, 40, 44, 132, 103, 205, 208, 158, 71, 219, 39, 80, 202, 244, 99, 99, 232, 151, 127, 27, 75, 12, 194, 193, 33, 76, 204, 88, 245, 148, 82, 163, 243, 211, 224, 104, 244, 0, 35, 243, 94, 10, 123, 147, 221, 171, 18, 178, 19, 232, 132, 215, 167, 159, 15, 50, 76, 85, 29, 4, 54, 82, 220, 3, 243, 249, 78, 66, 233, 61, 97, 239, 124, 182, 179, 147, 80]
vprKey = [37, 223, 232, 166, 117, 30, 117, 14, 47, 128, 243, 45, 184, 182, 227, 17, 0]


# ---------------------------------------------------------------------------
# KGM / KGMA / VPR decryption (pure standard library, zero external deps)
# ---------------------------------------------------------------------------
def _xor_lower_half_byte(x):
    return x ^ ((x & 0x0F) << 4)


def _mask_v1(offset):
    value = 0
    while offset >= 0x11:
        value ^= table1[offset % TABLE_SIZE]
        offset >>= 4
        value ^= table2[offset % TABLE_SIZE]
        offset >>= 4
    return value


def _mask_v2(offset):
    return tableV2[offset % TABLE_SIZE] ^ _mask_v1(offset >> 4)


def _decrypt_kgm_byte(enc, filekey, offset):
    return _xor_lower_half_byte(_mask_v2(offset) ^ enc ^ filekey[offset % 17])


def _decrypt_vpr_byte(enc, filekey, offset):
    return _decrypt_kgm_byte(enc, filekey, offset) ^ vprKey[offset % 17]


def decrypt_kgm(in_path, out_path):
    """Decrypt a .kgm / .kgma file. Returns the detected audio format string."""
    with open(in_path, 'rb') as f:
        header = f.read(0x3C)
        if len(header) < 0x3C:
            raise ValueError("file too small / not a KGM container")
        filekey = bytearray(17)
        filekey[0:16] = header[0x1C:0x2C]
        filekey[16] = 0
        header_len = struct.unpack_from('<I', header, 0x10)[0]
        f.seek(header_len)
        offset = 0
        with open(out_path, 'wb') as out:
            while True:
                block = f.read(1 << 16)
                if not block:
                    break
                b = bytearray(block)
                for i in range(len(b)):
                    b[i] = _decrypt_kgm_byte(b[i], filekey, offset + i)
                out.write(b)
                offset += len(b)
    return detect_format(out_path)


def decrypt_vpr(in_path, out_path):
    """Decrypt a .vpr file (KuGou VIP encrypted). Returns detected audio format."""
    with open(in_path, 'rb') as f:
        header = f.read(0x3C)
        if len(header) < 0x3C:
            raise ValueError("file too small / not a KGM container")
        filekey = bytearray(17)
        filekey[0:16] = header[0x1C:0x2C]
        filekey[16] = 0
        header_len = struct.unpack_from('<I', header, 0x10)[0]
        f.seek(header_len)
        offset = 0
        with open(out_path, 'wb') as out:
            while True:
                block = f.read(1 << 16)
                if not block:
                    break
                b = bytearray(block)
                for i in range(len(b)):
                    b[i] = _decrypt_vpr_byte(b[i], filekey, offset + i)
                out.write(b)
                offset += len(b)
    return detect_format(out_path)


# ---------------------------------------------------------------------------
# Output format detection
# ---------------------------------------------------------------------------
def detect_format(path):
    with open(path, 'rb') as f:
        head = f.read(4)
    if head[:4] == b'fLaC':
        return 'flac'
    if head[:3] == b'ID3' or (head[0] == 0xFF and (head[1] & 0xE0) == 0xE0):
        return 'mp3'
    if head[:4] == b'RIFF':
        return 'wav'
    if head[:4] == b'OggS':
        return 'ogg'
    if head[:4] == b'M4A ' or head[4:8] == b'ftyp':
        return 'm4a'
    return 'unknown'


def is_valid_audio(path):
    with open(path, 'rb') as f:
        head = f.read(4)
    return (
        head[:4] == b'fLaC'
        or head[:3] == b'ID3'
        or (head[0] == 0xFF and (head[1] & 0xE0) == 0xE0)
        or head[:4] == b'RIFF'
        or head[:4] == b'OggS'
    )


# ---------------------------------------------------------------------------
# KGG decryption (requires the user's local KuGou KGMusicV3.db + pysqlcipher3)
# This path is OPTIONAL and fully guarded: it never writes a file unless the
# decrypted output is a valid audio stream. If the DB / key is unavailable the
# caller is told to fall back to the KuGou client or an unlock-music tool.
# ---------------------------------------------------------------------------
def decrypt_kgg(in_path, out_path, db_path=None, master_key_hex=None):
    """
    Best-effort KGG decryption.

    KGG stores its per-file key inside the KuGou client database
    `%APPDATA%\\KuGou8\\KGMusicV3.db`, which is a SQLCipher store. To open it you
    need `pysqlcipher3` (a generic pip package) and the database master key.

    The master key may be supplied via `master_key_hex` (a 32-byte / 64-char hex
    string) or the environment variable `KGG_DB_MASTER_KEY`. The SQLCipher
    settings unlock-music uses for this DB are:
        PRAGMA cipher_page_size = 1024;
        PRAGMA cipher_use_hmac = OFF;
        PRAGMA cipher_kdf_algorithm = PBKDF2_HMAC_SHA1;
        PRAGMA cipher_hmac_algorithm = HMAC_SHA1;
        PRAGMA cipher_plaintext_header_size = 0;

    Once the DB is open, the per-file key is looked up by the file's hash and the
    same V2 XOR mask (see _decrypt_kgm_byte) is applied with that key as fileKey.

    Returns the detected audio format, or raises on any failure.
    """
    try:
        from pysqlcipher3 import dbapi2 as sqlcipher
    except Exception:
        raise RuntimeError(
            "pysqlcipher3 is required for KGG but not installed. "
            "Install it in an isolated venv: pip install pysqlcipher3 "
            "(needs the system SQLCipher library)."
        )

    if not db_path or not os.path.exists(db_path):
        raise RuntimeError("KGMusicV3.db not found; KGG needs the KuGou client key database.")
    key = master_key_hex or os.environ.get('KGG_DB_MASTER_KEY')
    if not key:
        raise RuntimeError(
            "KGG master key not provided. Set KGG_DB_MASTER_KEY (hex) or pass --kgg-key. "
            "The key is the one unlock-music / Kugo-Music-Converter embed for KGMusicV3.db."
        )

    # Open the SQLCipher DB and read the key map (schema varies by KuGou version;
    # try the common tables and surface a clear error if none match).
    con = sqlcipher.connect(db_path)
    cur = con.cursor()
    cur.execute("PRAGMA key = \"x'%s'\";" % key.strip())
    cur.execute("PRAGMA cipher_page_size = 1024;")
    cur.execute("PRAGMA cipher_use_hmac = OFF;")
    cur.execute("PRAGMA cipher_kdf_algorithm = PBKDF2_HMAC_SHA1;")
    cur.execute("PRAGMA cipher_hmac_algorithm = HMAC_SHA1;")
    cur.execute("PRAGMA cipher_plaintext_header_size = 0;")

    file_hash = file_md5(in_path)
    kgg_key = None
    for tbl, hash_col, key_col in (('key', 'hash', 'key'), ('keys', 'hash', 'key'),
                                   ('kgg_key', 'file_hash', 'key_bytes')):
        try:
            cur.execute("SELECT %s FROM %s WHERE %s = ?" % (key_col, tbl, hash_col), (file_hash,))
            row = cur.fetchone()
            if row and row[0]:
                kgg_key = bytes(row[0]) if not isinstance(row[0], str) else bytes.fromhex(row[0])
                break
        except Exception:
            continue
    con.close()
    if not kgg_key:
        raise RuntimeError("No KGG key found in KGMusicV3.db for this file (hash=%s)." % file_hash)

    # Apply the V2 XOR mask with the DB-derived key as fileKey.
    filekey = bytearray(17)
    filekey[0:16] = kgg_key[:16]
    filekey[16] = 0
    with open(in_path, 'rb') as f:
        header = f.read(0x3C)
        header_len = struct.unpack_from('<I', header, 0x10)[0]
        f.seek(header_len)
        offset = 0
        with open(out_path, 'wb') as out:
            while True:
                block = f.read(1 << 16)
                if not block:
                    break
                b = bytearray(block)
                for i in range(len(b)):
                    b[i] = _decrypt_kgm_byte(b[i], filekey, offset + i)
                out.write(b)
                offset += len(b)
    if not is_valid_audio(out_path):
        os.remove(out_path)
        raise RuntimeError("KGG decryption produced invalid audio (wrong key?); file left untouched.")
    return detect_format(out_path)


def file_md5(path):
    import hashlib
    h = hashlib.md5()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main():
    import argparse
    ap = argparse.ArgumentParser(description="Decrypt KuGou encrypted audio (KGM/KGMA/VPR; KGG best-effort).")
    ap.add_argument("input")
    ap.add_argument("output")
    ap.add_argument("--kgg-db", default=os.environ.get("KGG_DB"))
    ap.add_argument("--kgg-key", default=None)
    args = ap.parse_args()

    ext = os.path.splitext(args.input)[1].lower()
    try:
        if ext in (".kgm", ".kgma"):
            fmt = decrypt_kgm(args.input, args.output)
        elif ext == ".vpr":
            fmt = decrypt_vpr(args.input, args.output)
        elif ext == ".kgg":
            fmt = decrypt_kgg(args.input, args.output, args.kgg_db, args.kgg_key)
        else:
            print("UNSUPPORTED: %s" % ext, file=sys.stderr)
            return 2
    except Exception as e:
        print("FAILED: %s" % e, file=sys.stderr)
        return 1

    print("OK format=%s -> %s" % (fmt, args.output))
    return 0


if __name__ == '__main__':
    sys.exit(main())
