# Plagx Writing Companion for Sublime Text

**Free academic writing checks inside Sublime Text.** Plagx Writing Companion checks essays, theses and papers written in Markdown, plain text or LaTeX: citations and reference lists, BibTeX files, word limits, basic grammar and punctuation, and overall writing readiness.

By Plagiarism Checker X. For full plagiarism checks and AI-generated text detection, visit [Text Similarity Detector](https://plagiarismcheckerx.com/?utm_source=plagx-sublime). This free package does not detect plagiarism or AI-generated text.

---

## Installation

**Package Control:** open the Command Palette (`Ctrl+Shift+P` / `Cmd+Shift+P`), run **Package Control: Install Package** and choose **Plagx Writing Companion**.

**Manual:** download this repository and copy the folder into your Sublime `Packages` directory (**Preferences → Browse Packages…**), renamed to `Plagx Writing Companion`.

Requires Sublime Text 4.

## Features

### Draft checks as you type
Open any `.md`, `.txt` or `.tex` file and suggestions appear as squiggly underlines (red for errors, yellow for warnings, blue for notes):

- **Citations and references:** in-text citations with no matching reference entry, references that are never cited, a missing reference section, and *et al.* formatting (APA or MLA)
- **Word limits:** warnings when the draft goes over or under your minimum and maximum word counts (the reference list isn't counted)
- **Punctuation:** double spaces, spaces before punctuation, missing spaces after punctuation, repeated punctuation, unmatched brackets and quotes, mixed quote styles
- **Basic grammar:** repeated words, *a/an* mistakes, lowercase *i*, sentence capitals, commonly confused words
- **Structure:** long sentences, long or single-sentence paragraphs, and required headings
- **Passive voice** (optional)

**Hover** an underline to read the message. Many suggestions have a **Replace with…** link that applies the fix.

### Writing readiness
The status bar shows the word count, reading time and readiness of the open draft: **Ready**, **Ready with suggestions** or **Not ready**. Run **Plagx: Show Writing Readiness** for the full summary with the Flesch Reading Ease score.

### Citations and bibliography
- **Format BibTeX as Reference List:** turns a `.bib` file into an APA reference list or MLA Works Cited page
- **Check BibTeX References:** finds duplicate entries, missing authors, titles and years, and invalid DOIs. Optionally verifies each DOI online.
- **Insert Reference from DOI:** enter a DOI and insert the formatted reference, an in-text citation or a narrative citation

## Commands

Open the Command Palette and type **Plagx**:

| Command | What it does |
|---|---|
| Plagx: Check Draft | Checks the current file now |
| Plagx: Show Writing Readiness | Readiness summary, word count, reading time and readability |
| Plagx: Format BibTeX as Reference List | Opens a formatted APA or MLA list for a `.bib` file |
| Plagx: Check BibTeX References | Finds problems in a `.bib` file |
| Plagx: Insert Reference from DOI | Looks up a DOI and inserts a reference or citation |
| Plagx: Clear Suggestions | Removes all Plagx underlines |
| Preferences: Plagx Writing Companion Settings | Opens the settings |

## Settings

**Preferences → Package Settings → Plagx Writing Companion → Settings**

| Setting | Default | Description |
|---|---|---|
| `style` | `"apa"` | Citation style: `"apa"` or `"mla"` |
| `min_words` | `null` | Minimum word count |
| `max_words` | `null` | Maximum word count |
| `required_headings` | `[]` | Headings the draft must contain, e.g. `["Introduction", "Conclusion"]` |
| `checks` | all except passive voice | Check groups: `"length"`, `"references"`, `"punctuation"`, `"grammar"`, `"passive-voice"` |
| `selector` | Markdown, plain text, LaTeX | Scope selector for files checked automatically |
| `check_on` | `"type"` | `"type"`, `"save"` or `"manual"` |

Example for a 2,000–2,500 word APA essay:

```json
{
	"style": "apa",
	"min_words": 2000,
	"max_words": 2500,
	"required_headings": ["Introduction", "Conclusion"]
}
```

## Privacy

All draft and BibTeX checks run locally inside Sublime Text. Your text is never uploaded. The package connects to the internet only when you ask it to: **Insert Reference from DOI** and the optional online DOI check send the DOI to the public [Crossref API](https://www.crossref.org/). No accounts, API keys or telemetry are used.

## How it works

The package is a thin Sublime Text layer over two open-source Plagx libraries, bundled in `vendor/` so nothing needs to be installed with pip:

- [plagx-preflight](https://github.com/plagiarismcheckerx/plagx-preflight-python): draft checks, word counts, citation matching, grammar and punctuation
- [plagx-cite](https://github.com/plagiarismcheckerx/plagx-cite-python): APA and MLA formatting, BibTeX, DOI lookup and duplicate detection

The checks match the other Plagx tools exactly. Suggestions are rule-based, so always check them against your institution's style guide.

## What this package does not do

Plagx Writing Companion gives writing suggestions only. It does **not** check for plagiarism or detect AI-generated text. For full document checks, use [Text Similarity Detector](https://plagiarismcheckerx.com/?utm_source=plagx-sublime) or [download Plagiarism Checker X](https://plagiarismcheckerx.com/download?utm_source=plagx-sublime) for desktop.

## Development

```bash
python -m unittest discover -s tests
```

## License

[MIT](LICENSE) © 2026 Plagiarism Checker X
