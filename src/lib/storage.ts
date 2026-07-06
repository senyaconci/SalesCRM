import { randomUUID } from "crypto";
import { mkdir, writeFile, readFile } from "fs/promises";
import path from "path";

/**
 * File storage abstraction.
 *
 * - Local filesystem for development (default).
 * - Vercel Blob when `BLOB_READ_WRITE_TOKEN` is present (serverless hosts like
 *   Vercel have an ephemeral/read-only filesystem, so uploads must go to an
 *   external object store).
 *
 * The interface is intentionally small so an S3 backend can be added later
 * without changing call sites.
 */
export interface StoredFile {
  /** Public URL used by the app to fetch the file. */
  url: string;
  /** Original file name as uploaded. */
  fileName: string;
  /** Storage key / relative path within the backend. */
  key: string;
}

export interface FileStorage {
  save(file: File, keyPrefix?: string): Promise<StoredFile>;
  read(key: string): Promise<Buffer>;
}

function storageDir(): string {
  return (
    process.env.FILE_STORAGE_DIR ||
    path.join(process.cwd(), "storage", "uploads")
  );
}

function sanitizeFileName(name: string): string {
  return name.replace(/[^a-zA-Z0-9._-]/g, "_").slice(0, 120) || "file";
}

class LocalFileStorage implements FileStorage {
  async save(file: File, keyPrefix = "projects"): Promise<StoredFile> {
    const originalName = sanitizeFileName(file.name || "upload.bin");
    const key = `${keyPrefix}/${randomUUID()}-${originalName}`;
    const destPath = path.join(storageDir(), key);
    await mkdir(path.dirname(destPath), { recursive: true });

    const bytes = Buffer.from(await file.arrayBuffer());
    await writeFile(destPath, bytes);

    return {
      url: `/api/files/${key}`,
      fileName: originalName,
      key,
    };
  }

  async read(key: string): Promise<Buffer> {
    const safeKey = key.replace(/\.\.(\/|\\)/g, "");
    const filePath = path.join(storageDir(), safeKey);
    return readFile(filePath);
  }
}

/**
 * Vercel Blob backend. Returns the public blob URL directly, so the app fetches
 * files straight from blob storage (bypassing the local /api/files route).
 */
class BlobFileStorage implements FileStorage {
  async save(file: File, keyPrefix = "projects"): Promise<StoredFile> {
    const { put } = await import("@vercel/blob");
    const originalName = sanitizeFileName(file.name || "upload.bin");
    const key = `${keyPrefix}/${randomUUID()}-${originalName}`;
    const blob = await put(key, file, {
      access: "public",
      contentType: file.type || "application/octet-stream",
    });
    return { url: blob.url, fileName: originalName, key: blob.url };
  }

  async read(): Promise<Buffer> {
    // Blob URLs are public and served directly; the /api/files route is unused
    // in this mode.
    throw new Error("BlobFileStorage.read is not used; blob URLs are public.");
  }
}

export const fileStorage: FileStorage = process.env.BLOB_READ_WRITE_TOKEN
  ? new BlobFileStorage()
  : new LocalFileStorage();
