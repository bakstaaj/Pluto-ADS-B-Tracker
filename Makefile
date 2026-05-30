CFLAGS?=-O2 -g -Wall -W 
LDLIBS+=-liio -lpthread -lm -lad9361
PROGNAME=dump1090

all: dump1090

%.o: %.c
	$(CC) $(CFLAGS) -c $<

dump1090: dump1090.o anet.o
	$(CC) -g -o dump1090 dump1090.o anet.o $(LDFLAGS) $(LDLIBS)

clean:
	rm -f *.o dump1090

# Rebuild the HTTP server object whenever the embedded VRS web page changes.
dump1090.o: generated/vrs_web_assets.h
