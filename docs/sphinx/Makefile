# Mostlyright Python docs — Sphinx Makefile.
#
# Standard sphinx-build entry points + a `markdown` target wired for the
# Phase 15 W3 Starlight ingestion path. Run `make help` for the full list.
#
# You can set these variables from the command line, or set defaults via the
# environment.
SPHINXOPTS    ?=
SPHINXBUILD   ?= sphinx-build
SOURCEDIR     = .
BUILDDIR      = _build

# Put it first so that "make" without argument is like "make help".
help:
	@$(SPHINXBUILD) -M help "$(SOURCEDIR)" "$(BUILDDIR)" $(SPHINXOPTS) $(O)

.PHONY: help Makefile markdown html clean

# Catch-all target: route everything else to sphinx-build (handles html, dirhtml,
# linkcheck, etc.). The leading `@` keeps output clean for CI logs.
%: Makefile
	@$(SPHINXBUILD) -M $@ "$(SOURCEDIR)" "$(BUILDDIR)" $(SPHINXOPTS) $(O)

# Phase 15 W3 ingestion target — sphinx-markdown-builder emits MDX-friendly
# Markdown into _build/markdown/. `.github/workflows/docs-publish.yml`
# rsyncs _build/markdown/api/ into the landing repo's docs/sdk/python/ tree.
markdown:
	@$(SPHINXBUILD) -b markdown "$(SOURCEDIR)" "$(BUILDDIR)/markdown" $(SPHINXOPTS) $(O)
	@echo "Markdown output: $(BUILDDIR)/markdown"
