import { randomUUID } from "crypto";
import { mkdir, writeFile, readFile } from "fs/promises";
import path from "path";

/**
 * File storage abstraction.
 *
 * Phase 1 uses the local filesystem. The interface is intentionally small so a
 * later phase can swap in an S3 (or other object-store) backed implementation
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

export const fileStorage: FileStorage = new LocalFileStorage();
