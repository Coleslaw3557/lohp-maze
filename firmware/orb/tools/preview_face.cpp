// Host-side render of face_olmec.h — writes raw RGB888.
// Usage: preview_face out.rgb [gx gy dil glow jaw talkGlow breath mood blink wild talkPhase]
#include <cstdio>
#include <cstdlib>
#include <cstring>

#include "../face_olmec.h"

int main(int argc, char **argv) {
  static uint16_t base[olmec::W * olmec::H], fb[olmec::W * olmec::H];
  static uint16_t jawTile[olmec::JAW_TILE_W * olmec::JAW_TILE_H];
  olmec::renderBase(base);
  olmec::renderJawTile(jawTile);
  memcpy(fb, base, sizeof(fb));
  olmec::FaceState s;
  float breath = 0.5f;
  if (argc > 2) s.gx = atof(argv[2]);
  if (argc > 3) s.gy = atof(argv[3]);
  if (argc > 4) s.dil = atof(argv[4]);
  if (argc > 5) s.glow = atof(argv[5]);
  if (argc > 6) s.jaw = atof(argv[6]);
  if (argc > 7) s.talkGlow = atof(argv[7]);
  if (argc > 8) breath = atof(argv[8]);
  if (argc > 9) s.mood = atof(argv[9]);
  if (argc > 10) s.blink = atof(argv[10]);
  if (argc > 11) s.wild = atof(argv[11]);
  if (argc > 12) s.talkPhase = atof(argv[12]);
  olmec::drawEyes(fb, base, s);
  olmec::drawJaw(fb, base, jawTile, s);
  olmec::nostrilBreath(fb, base, breath);
  FILE *f = fopen(argv[1], "wb");
  for (int i = 0; i < olmec::W * olmec::H; i++) {
    uint16_t c = fb[i];
    unsigned char px[3] = {(unsigned char)(((c >> 11) & 0x1F) << 3), (unsigned char)(((c >> 5) & 0x3F) << 2),
                           (unsigned char)((c & 0x1F) << 3)};
    fwrite(px, 1, 3, f);
  }
  fclose(f);
  return 0;
}
