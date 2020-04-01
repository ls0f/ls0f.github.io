
BASEDIR=$(CURDIR)
OUTPUTDIR=$(BASEDIR)/docs
GITHUB_PAGES_BRANCH=master
THEME=journal

debug:
	hugo server --theme=$(THEME) --buildDrafts --watch

publish:
	rm -rf $(OUTPUTDIR)
	hugo -t $(THEME)

github: publish
	ghp-import -m "Generate hugo site" -b $(GITHUB_PAGES_BRANCH) $(OUTPUTDIR)
	git push origin $(GITHUB_PAGES_BRANCH) --force
