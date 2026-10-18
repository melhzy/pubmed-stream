# Troubleshooting

Find the message or symptom you see. Most problems happen during setup and are fixed in a minute.

## Installing and starting

| You see | What it means and what to do |
|---|---|
| `'python' is not recognized` (Windows) or `command not found: python` (Mac) | Python is not installed, or the terminal cannot find it. On Windows, run the Python installer again, choose **Modify**, and make sure **Add Python to environment variables** is ticked, then open a new terminal. On a Mac, type `python3` instead of `python`. |
| `'pip' is not recognized` | Use `python -m pip` instead of `pip`, as the [setup guide](setup.md) does. |
| `'jupyter' is not recognized` | Use `python -m notebook` to start Jupyter. |
| `ERROR: file:///... does not appear to be a Python project` | The terminal is not in the pubmed-stream folder. `cd` into the folder that holds `pyproject.toml`, then install again. |
| `ModuleNotFoundError: No module named 'tutorial_utils'` | The notebook was opened from outside the `tutorials` folder. Start Jupyter from the pubmed-stream folder and open the notebook inside `tutorials`. |
| `ModuleNotFoundError: No module named 'matplotlib'` (or `pandas`, `networkx`) | The tutorial tools are not installed. Run `python -m pip install -e ".[tutorials]"` in the pubmed-stream folder. |
| A command-line search with a quoted phrase finds unrelated papers or fails, on Windows | Windows PowerShell drops the inner double quotes of `'"gut microbiota"[Title]'`, and Command Prompt does not understand single quotes. In Windows PowerShell, put a backslash before each inner quote: `'\"gut microbiota\"[Title] AND frailty[Title/Abstract]'`. In Command Prompt, use double quotes outside: `"\"gut microbiota\"[Title] AND frailty[Title/Abstract]"`. The notebooks avoid the problem. |
| Jupyter opens a page in the browser, then stops working | The terminal that started it was closed. Start it again with `python -m notebook`. |

## Running a notebook

| You see | What it means and what to do |
|---|---|
| `NameError: name 'QUERY' is not defined` (or another setting) | The cells were run out of order, or the settings cell was skipped. Run the whole notebook from the top: **Run > Run All Cells**. |
| Changed settings, but the results did not change | Earlier results were still in memory. Choose **Kernel > Restart Kernel and Run All Cells** (in Colab, **Runtime > Restart session and run all**). |
| A cell shows `[*]` for many minutes | It is waiting for NCBI. Large downloads take a few minutes; an [API key](setup.md#getting-a-free-ncbi-api-key) makes them three times faster. If nothing changes for ten minutes, choose **Kernel > Interrupt Kernel** and run the cell again. |
| Pink boxes with `429 Client Error: Too Many Requests` | NCBI asked pubmed-stream to slow down, and it waited and retried. This is normal and harmless unless the cell fails. To avoid it, add an API key, and don't run several notebooks at once. |
| `SyntaxError` in the settings cell | A quote or bracket is missing. Text goes between straight quotes, `"like this"`. A search that contains double quotes goes between single quotes: `'"gut microbiota"[Title]'`. |
| `ConnectionError`, `SSLError` or `Max retries exceeded` | The computer cannot reach NCBI. Check the internet connection. On a university or hospital network, a firewall may block it: try another network, or ask IT whether a proxy is needed. They can tell you the value to put in an `HTTPS_PROXY` environment variable. |

## Searches and downloads

| You see | What it means and what to do |
|---|---|
| A search finds 0 articles | Check the spelling, quotes and brackets. Paste the search into [PMC's website](https://pmc.ncbi.nlm.nih.gov/) to test it; its *Advanced* search builds field tags for you. A MeSH heading must be spelled exactly as in the [MeSH browser](https://www.ncbi.nlm.nih.gov/mesh). |
| A search finds tens of thousands of articles | It is too broad. Put the main concept in the title with `[Title]`, add `AND` terms, or use MeSH headings. Tutorial 2 shows how, step by step. |
| Many articles are *unavailable* | Their publishers do not allow full-text download. Add `AND "open access"[filter]` to the search, or accept that they will be missing. |
| Only recent papers were downloaded | Searches return the newest matches first. Raise the number of articles, add a date range such as `AND 2010:2018[pdat]`, or add a key paper to bring in the older literature. |
| Some names show odd characters such as `Ã©` in Excel | Excel opened the CSV with the wrong encoding. The tutorials save CSVs that Excel reads correctly; for other CSVs, use **Data > From Text/CSV** in Excel and choose *UTF-8*. |

## Google Colab

| You see | What it means and what to do |
|---|---|
| *Warning: This notebook was not authored by Google* | Colab asks before running notebooks from GitHub. Choose **Run anyway**. |
| Results or downloads disappeared | Colab deletes everything when the session ends. Run the notebook again, and save what you want to keep with the notebook's last cell or **File > Download**. |
| The zip file did not download | The browser blocked it. Allow downloads from `colab.research.google.com`, then run the last cell again. |

## Obsidian

| You see | What it means and what to do |
|---|---|
| The vault opens, but there are no notes | You opened the folder above the graph. Open the `kg_<topic>` folder itself, the one that holds `PubMed Stream.md`. |
| The graph view is a crowded ball of dots | Most dots are cited papers without a note. Switch on **Existing files only** under *Filters* in the graph settings, filter further with `path:papers`, and spread it with the *Forces* sliders. See the [Obsidian guide](obsidian.md#the-graph-view). |
| The graph has no colours | Colours are set when the graph is first built, and only if the vault has none yet. Add them yourself under **Groups** in the graph settings. |
| Clicking a link creates an empty note | The paper is cited but was not downloaded or added as a stub. Its PubMed ID is in the link's name. Delete the empty note if you don't need it. |
| Notes I wrote disappeared after a rebuild | They were inside the generated block, between the `%% pubmed-stream:start` and `%% pubmed-stream:end` lines. Write below the end line; see [write your own notes](obsidian.md#write-your-own-notes). |

| `Command line interface is not enabled` from `obsidian` | Obsidian's own command line is off. In Obsidian, open **Settings > General**, switch on *Command line interface*, follow the prompt, and open a new terminal. |
| `pubmed-stream open` says Obsidian does not know the graph | Obsidian opens only folders it already knows. Add the `kg_<topic>` folder once with **Open folder as vault**; after that, `open` works. |

## AI assistants

| You see | What it means and what to do |
|---|---|
| The assistant says it has no pubmed-stream tools | The MCP server did not start. Run `pubmed-stream init` in the folder and start the assistant there again. In Claude Code, `/mcp` shows the server and any error; approve it if asked. In Codex, `/mcp` lists the tools. |
| `init` works, but the server fails to start later | The settings point to the Python that ran `init`. If you moved or removed that Python environment, run `pubmed-stream init` again from the one you use now. |
| Codex ignores the model I set in the research folder | Codex 0.163 does not read a folder's model setting. Choose it with `/model` during the session, start with `codex -m <model>`, or set `model` in the `config.toml` of the `.codex` folder in your home folder. |
| Codex stops at `download` or `build_knowledge_graph` | Tools that save files need your approval. Approve them when asked; in `codex exec`, add `--approve-for-me`. |
| The assistant cites a paper you cannot find | Ask which tool output it read the paper in. Open `https://pubmed.ncbi.nlm.nih.gov/<PMID>/`; if the PMID is not among the downloads (`pubmed-stream list publications --id <PMID>`), do not rely on the claim. |

## Local models with Ollama

| You see | What it means and what to do |
|---|---|
| `Ollama is not running` | Start Ollama from its icon or with `ollama serve`, or install it from [ollama.com](https://ollama.com). |
| `Ollama does not have the model` | Download it once: `ollama pull hf.co/unsloth/Llama-3.2-1B-Instruct-GGUF:Q4_K_M`, or name a model you have with `--model`; `ollama list` shows them. |
| A summary ends with `[cut at 300 tokens]` | The model started repeating itself and was stopped. Read the abstract instead, or try a larger model. |
| A warning that the prompt filled the model's context | The abstract was too long for the model's working memory and was cut. Add `--num-ctx 16384`. |
| Reviews are very slow | Without a graphics card, a model reads a few hundred words a second. Review fewer papers at a time with `--id`. |

Still stuck? Open an [issue on GitHub](https://github.com/melhzy/pubmed-stream/issues) with the message you see and what you were doing.
