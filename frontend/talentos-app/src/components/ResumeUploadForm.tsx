import { useRef, useState } from "react";
import Button from "./ui/Button";
import { UploadIcon } from "./ui/icons";

interface Props {
  loading: boolean;
  onSubmit: (file: File) => void;
}

export default function ResumeUploadForm({ loading, onSubmit }: Props) {
  const [file, setFile] = useState<File | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!file) return;
    onSubmit(file);
  }

  function handleDrop(e: React.DragEvent) {
    e.preventDefault();
    setDragOver(false);
    const dropped = e.dataTransfer.files?.[0];
    if (dropped) setFile(dropped);
  }

  return (
    <form onSubmit={handleSubmit} className="jd-form">
      <label>Resume file (PDF or DOCX)</label>
      <div
        className={`dropzone ${dragOver ? "dropzone--active" : ""} ${file ? "dropzone--filled" : ""}`}
        onClick={() => inputRef.current?.click()}
        onDragOver={(e) => {
          e.preventDefault();
          setDragOver(true);
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={handleDrop}
      >
        <UploadIcon width={26} height={26} />
        {file ? (
          <div className="dropzone__filename">{file.name}</div>
        ) : (
          <>
            <p>
              <strong>Click to browse</strong> or drag and drop
            </p>
            <p className="hint-text">PDF or DOCX, up to 10MB</p>
          </>
        )}
        <input
          ref={inputRef}
          type="file"
          accept=".pdf,.docx,.doc"
          hidden
          onChange={(e) => setFile(e.target.files?.[0] || null)}
        />
      </div>
      <Button type="submit" icon={<UploadIcon width={16} height={16} />} loading={loading} disabled={!file}>
        Analyze resume
      </Button>
    </form>
  );
}
