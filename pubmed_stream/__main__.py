"""Allow ``python -m pubmed_stream`` as a shorthand for the CLI."""

from pubmed_stream.cli import main

raise SystemExit(main())
