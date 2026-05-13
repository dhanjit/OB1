-- Open Brain local schema
--
-- Embedding dimension defaults to 768 (Ollama nomic-embed-text).
-- To use a different model, change EMBEDDING_DIM below and rebuild the
-- container volume, or run an ALTER TABLE / DROP FUNCTION + recreate.
--
-- Known dims: nomic-embed-text=768, mxbai-embed-large=1024,
--             rjmalagon/gte-qwen2-1.5b-instruct-embed-f16=1536.

CREATE TABLE IF NOT EXISTS thoughts (
  id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
  content text NOT NULL,
  embedding vector(768),
  metadata jsonb DEFAULT '{}'::jsonb,
  content_fingerprint text,
  created_at timestamptz DEFAULT now(),
  updated_at timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS thoughts_embedding_hnsw
  ON thoughts USING hnsw (embedding vector_cosine_ops);

CREATE INDEX IF NOT EXISTS thoughts_metadata_gin
  ON thoughts USING gin (metadata);

CREATE INDEX IF NOT EXISTS thoughts_created_at_idx
  ON thoughts (created_at DESC);

CREATE UNIQUE INDEX IF NOT EXISTS thoughts_fingerprint_uniq
  ON thoughts (content_fingerprint)
  WHERE content_fingerprint IS NOT NULL;

CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS trigger AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS thoughts_updated_at ON thoughts;
CREATE TRIGGER thoughts_updated_at
  BEFORE UPDATE ON thoughts
  FOR EACH ROW
  EXECUTE FUNCTION update_updated_at();
