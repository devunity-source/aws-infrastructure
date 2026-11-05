// Client-side search over guide titles, descriptions, categories and tags.
// Every query word must match a word in the guide (as a prefix, so typing "ultra" finds "ultrabook").
// Words are compared in a normalised form: plurals folded ("monitors" -> "monitor") and a few
// synonyms joined ("mice" -> "mouse"), so "mouse" finds the gaming mice guide too.

export interface SearchDoc { href: string; title: string; description: string; category: string; tags: string }

const SYNONYMS: Record<string, string> = {
  mice: 'mouse', mouses: 'mouse',
  notebook: 'laptop', ultrabook: 'laptop',
  headset: 'headphone', earphone: 'earbud',
  mic: 'microphone', webcam: 'camera', cam: 'camera',
  hub: 'dock', powerbank: 'power',
};

export function norm(word: string): string {
  let w = word.toLowerCase();
  if (SYNONYMS[w]) return SYNONYMS[w];
  if (w.length > 4 && w.endsWith('ies')) w = `${w.slice(0, -3)}y`;
  else if (w.length > 4 && /(ch|sh|x|ss)es$/.test(w)) w = w.slice(0, -2);
  else if (w.length > 3 && w.endsWith('s') && !w.endsWith('ss')) w = w.slice(0, -1);
  return SYNONYMS[w] ?? w;
}

export function words(text: string): string[] {
  return (text.toLowerCase().match(/[a-z0-9]+/g) ?? []).map(norm);
}

/** Matching guides, best first: title matches count most, then tags and category, then description. */
export function search<T extends SearchDoc>(docs: T[], query: string): T[] {
  const terms = words(query);
  if (!terms.length) return docs;
  const scored: { doc: T; score: number; i: number }[] = [];
  docs.forEach((doc, i) => {
    const fields: [string[], number][] = [
      [words(doc.title), 3], [words(`${doc.tags} ${doc.category}`), 2], [words(doc.description), 1],
    ];
    let score = 0;
    for (const t of terms) {
      // A whole-word match beats a prefix match.
      const best = Math.max(...fields.map(([ws, w]) =>
        ws.includes(t) ? w * 2 : ws.some((x) => x.startsWith(t) || norm(x).startsWith(t)) ? w : 0));
      if (!best) return;
      score += best;
    }
    scored.push({ doc, score, i });
  });
  return scored.sort((a, b) => b.score - a.score || a.i - b.i).map((s) => s.doc);
}
