const ADJECTIVES = [
  "bold", "brave", "bright", "calm", "clever", "cool", "cosmic", "crisp",
  "daring", "deep", "eager", "fair", "fast", "fresh", "golden", "grand",
  "happy", "keen", "lunar", "mighty", "noble", "pure", "quick", "quiet",
  "rapid", "sharp", "silent", "solar", "solid", "steady", "storm", "swift",
  "vivid", "wild", "wise", "zen",
];

const NOUNS = [
  "badger", "bear", "bee", "bird", "blaze", "breeze", "comet", "crane",
  "dolphin", "dragon", "eagle", "elk", "falcon", "fox", "gecko", "hawk",
  "ibis", "jaguar", "kite", "koi", "lion", "lynx", "mammoth", "manta",
  "newt", "octopus", "orca", "owl", "panda", "panther", "phoenix", "puma",
  "raven", "shark", "sparrow", "tiger",
];

export function randomAgentName(): string {
  const adj = ADJECTIVES[Math.floor(Math.random() * ADJECTIVES.length)];
  const noun = NOUNS[Math.floor(Math.random() * NOUNS.length)];
  return `${adj}-${noun}`;
}
