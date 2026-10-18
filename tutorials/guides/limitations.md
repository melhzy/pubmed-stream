# What pubmed-stream can and cannot do

pubmed-stream is a fast way to **map** a literature: to find what exists, see how it connects, and decide what to read. It does not read papers for you or judge their quality, and the map has blind spots. Knowing them lets you use the results with confidence.

## What it covers

**Full text comes only from PubMed Central.** PMC holds the papers that publishers and authors deposit there, mostly open-access papers and NIH-funded manuscripts. Many important papers, especially older ones and those in subscription journals, are not in PMC or cannot be downloaded from it. pubmed-stream counts these as *unavailable*, not as errors.

**Papers it cannot download can still appear.** Papers in a key paper's neighborhood join the knowledge graph as **stubs**, with PubMed's details and links but no abstract or full text. Other cited papers appear only as links to a note that does not exist, which Obsidian shows as faint dots in the graph view. Landmark papers often appear in these ways, so open their PubMed pages before dismissing them.

**Searches return the newest papers first.** `max_results=30` downloads the 30 newest matches, not the 30 most important. Older foundational work enters the graph through citations and key papers, which is why tutorial 0 picks the most cited reference as its key paper. To reach back in time, raise the number or add a date range such as `AND 2010:2018[pdat]`.

**Citation links are only as complete as the reference lists.** A link is made when a reference has a PubMed ID or DOI that matches another paper in the graph. References without identifiers, such as books and some conference papers, are not linked.

**"Most cited" means most cited inside your graph.** It measures how much your study's literature relies on a paper, which is useful for orientation but is not the paper's overall citation count or impact.

**MeSH indexing lags.** NLM indexes new papers weeks to months after publication, and the newest papers in a graph often have no MeSH headings yet. They are missing from concept notes and from MeSH searches until then. Combine word and MeSH searches with `OR`, as tutorial 2 shows.

**Similarity is PubMed's.** *Similar articles* come from PubMed's word-and-MeSH algorithm. Its scores rank papers within one list and do not compare across lists.

**Retraction flags are PubMed's.** pubmed-stream flags a paper as retracted when PubMed marks it as retracted or links a retraction notice. Expressions of concern, errata and corrections are not flagged. Check the publisher's page for anything you will rely on.

**Evidence labels are approximate.** Tutorial 0's evidence chart groups papers by their publication types and MeSH headings, so it inherits PubMed's labels and indexing gaps. It shows the shape of a field, not an evidence grade for any paper.

## What it is not

**Not a systematic review.** A systematic review needs a registered protocol, searches of several databases (such as Embase, Web of Science and Cochrane CENTRAL as well as PubMed), screening by two reviewers, risk-of-bias assessment and a PRISMA flow diagram. pubmed-stream helps with the first steps, scoping the field and testing searches, and its searches are recorded in each graph's `.pubmed-stream/study.json` for your methods section. It does not replace the rest.

**Not a judge of quality.** A paper in the graph, however connected, may be small, biased or wrong. Read the paper itself before citing it, never only its metadata or abstract.

**A snapshot in time.** PubMed and PMC change every day. The same search returns different papers next month, which is why the knowledge graph can be refreshed.

## Using the downloads responsibly

**Licences vary.** Papers in PMC's open-access subset carry licences such as CC BY, which allows reuse with attribution, or CC BY-NC, which forbids commercial reuse. Downloading them for your own research is fine; check each paper's licence before redistributing its text.

**Respect NCBI's limits.** pubmed-stream keeps within NCBI's request rate automatically. For very large downloads, tens of thousands of papers, NCBI asks people to use the [PMC bulk download service](https://pmc.ncbi.nlm.nih.gov/tools/openftlist/) instead of the E-utilities.
