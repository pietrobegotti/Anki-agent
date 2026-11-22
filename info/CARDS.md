# Instructions for the LLM

- When the user asks for the meaning of one or more words, prepare one complete card per word as a readable response. Show all field values and examples, then ask the user to confirm.
- Do not write card files before confirmation. After confirmation, save each approved card as its own JSON file directly in `cards/`, using the exact content shown to the user.
- Use the JSON template below. Do not add, remove, or rename fields. The square-bracketed text is instructional placeholder text: replace it with real values and never copy the brackets into a card.
- Name each file `<id>_<word>.json`, using the Japanese word in the filename. Use a six-digit progressive ID: start at `000001` if `cards/` has no card files; otherwise use the next ID. Never reuse an ID or overwrite a file. The IDs in the examples below are illustrative and do not count as files in `cards/`.
- Write only valid JSON to the file. Do not include Markdown fences or prose in the JSON file. Do not ask the user to run a script.

## JSON template

```json
{
  "id": "[six-digit progressive ID]",
  "word": "[Japanese word]",
  "furigana": "[reading of the whole word]",
  "translation": "[Italian translation, or the language requested by the user]",
  "meaning": "[very concise note about nuance, usage, or connotation; not a definition]",
  "compound": "[for a long compound: subword：Italian translation\nsubword：Italian translation; otherwise empty]",
  "synonyms": "[zero to three synonyms; empty for compounds]",
  "antonyms": "[zero to three antonyms; empty for compounds]",
  "kanji": "[kanji]\t[Takoboto reading]\t[Takoboto translation]\n[kanji]\t[Takoboto reading]\t[Takoboto translation]",
  "example": "[Japanese sentence or phrase] — [Italian translation]\n[Japanese sentence or phrase] — [Italian translation]\n[Japanese sentence or phrase] — [Italian translation]"
}
```

## Field rules

- `meaning`: describe the word's nuance or use in a very concise note. Do not give a dictionary definition or repeat the translation. For `処置`, for example: `Si usa quando si prende una misura concreta per affrontare un problema o una situazione, spesso in ambito medico o pratico.`
- `compound`: for a long compound, split it into meaningful subwords and give each subword's Italian translation on its own line, in the format `subword：translation`. Example: `伝統：tradizione\n工芸：arti e mestieri artigianali`. Leave this field empty when the word is not a long compound.
- `synonyms` and `antonyms`: provide zero to three suitable words, separated by commas. Leave both fields empty for any compound, even when `compound` itself is empty. For a non-compound, leave a field empty if no suitable words are available.
- `kanji`: read `info/Takoboto.enriched.json`. For each distinct kanji in `word`, find the list item keyed by that kanji and copy its `reading` and `translation` exactly. Keep the kanji in word order, one per line. Separate the kanji, reading, and translation with tabs (`\t`); separate kanji lines with newlines (`\n`). If a kanji is missing from Takoboto, ask the user before creating the card; do not invent its data.
- `example`: include exactly three Japanese sentences or phrases using the word. Put the Italian translation on the same line, after ` — `.
- `id`: use a six-digit string matching the filename and the next unused progressive ID.

## Examples

### `000001_伝統工芸.json`

```json
{
  "id": "000001",
  "word": "伝統工芸",
  "furigana": "でんとうこうげい",
  "translation": "artigianato tradizionale",
  "meaning": "Evoca saperi locali tramandati tra generazioni.",
  "compound": "伝統：tradizione\n工芸：arti e mestieri artigianali",
  "synonyms": "",
  "antonyms": "",
  "kanji": "伝\tデン, テン; つた.わる, つた.える, つた.う, つだ.う, -づた.い, つて\ttransmit, go along, walk along, follow, report, communicate, legend, tradition\n統\tトウ; す.べる\toverall, relationship, ruling, governing\n工\tコウ, ク, グ\tartigianato, costruzione, katakana e radicale (n. 48)\n芸\tゲイ, ウン; う.える, のり, わざ\ttechnique, art, craft, performance, acting, trick, stunt",
  "example": "京都の伝統工芸を見学した。 — Ho ammirato l'artigianato tradizionale di Kyoto.\nこの地域では伝統工芸が受け継がれている。 — In questa regione si tramandano le arti artigianali tradizionali.\n伝統工芸の職人に話を聞いた。 — Ho parlato con un artigiano tradizionale."
}
```

### `000002_静か.json`

```json
{
  "id": "000002",
  "word": "静か",
  "furigana": "しずか",
  "translation": "tranquillo; silenzioso; calmo",
  "meaning": "Trasmette una quiete composta e spesso piacevole, non solo assenza di rumore.",
  "compound": "",
  "synonyms": "穏やか (calmo), 物静か (tranquillo e riservato), 閑静 (quieto, riferito a un luogo)",
  "antonyms": "賑やか (animato), 騒がしい (rumoroso), うるさい (chiassoso)",
  "kanji": "静\tセイ, ジョウ; しず-, しず.か, しず.まる, しず.める\tquiet",
  "example": "静かな町で暮らしたい。 — Vorrei vivere in una città tranquilla.\n図書館では静かにしてください。 — Per favore, fate silenzio in biblioteca.\n彼女は静かな声で話した。 — Parlò con voce calma."
}
```

### `000003_日.json`

```json
{
  "id": "000003",
  "word": "日",
  "furigana": "ひ",
  "translation": "giorno",
  "meaning": "Da solo suona più quotidiano; nei composti cambiano spesso lettura e sfumatura.",
  "compound": "",
  "synonyms": "",
  "antonyms": "",
  "kanji": "日\tニチ, ジツ; ひ, -び, -か\tgiorno, sole, Giappone, contatore dei giorni",
  "example": "今日は休みです。 — Oggi è giorno di riposo.\n日が長くなりました。 — Le giornate si sono allungate.\n毎日、日本語を勉強しています。 — Studio giapponese ogni giorno."
}
```

For `処置`, the user-provided nuance is: `Si usa quando si prende una misura concreta per affrontare un problema o una situazione, spesso in ambito medico o pratico.` The current Takoboto file has no entry for `処`; do not create a complete `処置` card until that kanji's data is available.
