import { useEffect, useState, type ReactNode } from "react";

interface GlossaryEntry {
  term: string;
  description: string;
  interpretation: string;
}

interface Props {
  term: string;
  children: ReactNode;
}

let glossaryCache: Record<string, GlossaryEntry> | null = null;
let glossaryPromise: Promise<Record<string, GlossaryEntry>> | null = null;

function fetchGlossary(): Promise<Record<string, GlossaryEntry>> {
  if (glossaryCache) return Promise.resolve(glossaryCache);
  if (glossaryPromise) return glossaryPromise;

  glossaryPromise = fetch("/api/glossary")
    .then((res) => res.json())
    .then((json: { data: GlossaryEntry[] }) => {
      const map: Record<string, GlossaryEntry> = {};
      for (const entry of json.data ?? []) {
        map[entry.term.toLowerCase()] = entry;
      }
      glossaryCache = map;
      return map;
    })
    .catch(() => {
      glossaryPromise = null;
      return {} as Record<string, GlossaryEntry>;
    });

  return glossaryPromise;
}

/** Reset module-level cache. Only used in tests. */
export function _resetGlossaryCache() {
  glossaryCache = null;
  glossaryPromise = null;
}

export function GlossaryTooltip({ term, children }: Props) {
  const [entry, setEntry] = useState<GlossaryEntry | null>(null);
  const [show, setShow] = useState(false);

  useEffect(() => {
    let cancelled = false;
    fetchGlossary().then((map) => {
      if (!cancelled) {
        setEntry(map[term.toLowerCase()] ?? null);
      }
    });
    return () => {
      cancelled = true;
    };
  }, [term]);

  if (!entry) {
    return <>{children}</>;
  }

  return (
    <span
      style={{ position: "relative", cursor: "help" }}
      onMouseEnter={() => setShow(true)}
      onMouseLeave={() => setShow(false)}
      data-testid={`glossary-${term}`}
    >
      <span style={{ textDecoration: "underline dotted" }}>{children}</span>
      {show && (
        <span
          role="tooltip"
          style={{
            position: "absolute",
            bottom: "100%",
            left: 0,
            marginBottom: 6,
            padding: "8px 12px",
            background: "#1a1a2e",
            color: "#eee",
            borderRadius: 6,
            fontSize: 13,
            lineHeight: 1.4,
            width: 260,
            zIndex: 1000,
            boxShadow: "0 2px 8px rgba(0,0,0,0.25)",
            pointerEvents: "none",
          }}
        >
          <strong>{entry.term}</strong>
          <br />
          {entry.description}
          {entry.interpretation && (
            <>
              <br />
              <em style={{ color: "#aab" }}>{entry.interpretation}</em>
            </>
          )}
        </span>
      )}
    </span>
  );
}
