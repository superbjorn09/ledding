#ifndef IPADDRESS_H_MOCK
#define IPADDRESS_H_MOCK

#include <cstdint>

class IPAddress {
public:
	IPAddress() {}
	IPAddress(uint8_t a, uint8_t b, uint8_t c, uint8_t d) {
		(void)a; (void)b; (void)c; (void)d;
	}
};

#endif /* IPADDRESS_H_MOCK */
