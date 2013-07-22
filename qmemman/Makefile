PYTHON_QUBESPATH = $(PYTHON_SITEPATH)/qubes
SYSCONFDIR ?= /etc
UNITDIR ?= /usr/lib/systemd/system

all: meminfo-writer
	python -m compileall .
	python -O -m compileall .

meminfo-writer: meminfo-writer.o
	$(CC) -g -o meminfo-writer meminfo-writer.o -lxenstore

clean:
	rm -f *.pyo 

install:
ifndef PYTHON_SITEPATH
	$(error PYTHON_SITEPATH not defined)
endif
	mkdir -p $(DESTDIR)$(PYTHON_QUBESPATH)
	cp qmemman*py $(DESTDIR)$(PYTHON_QUBESPATH)
	cp qmemman*py[co] $(DESTDIR)$(PYTHON_QUBESPATH)
	mkdir -p $(DESTDIR)$(SYSCONFDIR)/qubes
	cp qmemman.conf $(DESTDIR)$(SYSCONFDIR)/qubes/
	mkdir -p $(DESTDIR)/usr/lib/qubes
	cp server.py $(DESTDIR)/usr/lib/qubes/qmemman_daemon.py
	cp meminfo-writer $(DESTDIR)/usr/lib/qubes/
	mkdir -p $(DESTDIR)$(UNITDIR)
	cp qubes-meminfo-writer.service $(DESTDIR)$(UNITDIR)
	cp qubes-qmemman.service $(DESTDIR)$(UNITDIR)

