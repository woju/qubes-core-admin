UNITDIR ?= /usr/lib/systemd/system

all:
	true

install:
	mkdir -p $(DESTDIR)$(UNITDIR)
	cp qubes-block-cleaner.service $(DESTDIR)$(UNITDIR)
	cp qubes-core.service $(DESTDIR)$(UNITDIR)
	cp qubes-setupdvm.service $(DESTDIR)$(UNITDIR)
	cp qubes-meminfo-writer.service $(DESTDIR)$(UNITDIR)
	cp qubes-netvm.service $(DESTDIR)$(UNITDIR)
	cp qubes-qmemman.service $(DESTDIR)$(UNITDIR)
