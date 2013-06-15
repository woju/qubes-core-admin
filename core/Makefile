PYTHON_QUBESPATH = $(PYTHON_SITEPATH)/qubes

all:
	python -m compileall .
	python -O -m compileall .

install:
ifndef PYTHON_SITEPATH
	$(error PYTHON_SITEPATH not defined)
endif
	mkdir -p $(DESTDIR)$(PYTHON_QUBESPATH)
	cp qubes.py $(DESTDIR)$(PYTHON_QUBESPATH)
	cp qubes.py[co] $(DESTDIR)$(PYTHON_QUBESPATH)
	cp qubesutils.py $(DESTDIR)$(PYTHON_QUBESPATH)
	cp qubesutils.py[co] $(DESTDIR)$(PYTHON_QUBESPATH)
	cp guihelpers.py $(DESTDIR)$(PYTHON_QUBESPATH)
	cp guihelpers.py[co] $(DESTDIR)$(PYTHON_QUBESPATH)
	cp __init__.py $(DESTDIR)$(PYTHON_QUBESPATH)
	cp __init__.py[co] $(DESTDIR)$(PYTHON_QUBESPATH)
