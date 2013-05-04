CC=gcc
CFLAGS=-Wall
all: xenstore-watch
xenstore-watch: xenstore-watch.o
	$(CC) -o xenstore-watch xenstore-watch.o -lxenstore

clean:
	rm -f *.o *~ qubes-restore xenstore-watch xenfreepages

