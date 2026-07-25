// Host-side render of face_olmec.h — writes raw RGB888.
// Usage: preview_face out.rgb [gx gy dil glow jaw talkGlow breath mood blink wild talkPhase scene]
//        preview_face --menu out.rgb [wedge amt]   (the touch menu; wedge -1..4,
//                                                   amt = press/charge glow)
#include <cstdio>
#include <cstdlib>
#include <cstring>

#include "../face_olmec.h"
#include "../menu_olmec.h"

static void writeRgb(const char *path, const uint16_t *fb) {
  FILE *f = fopen(path, "wb");
  for (int i = 0; i < olmec::W * olmec::H; i++) {
    uint16_t c = fb[i];
    unsigned char px[3] = {(unsigned char)(((c >> 11) & 0x1F) << 3), (unsigned char)(((c >> 5) & 0x3F) << 2),
                           (unsigned char)((c & 0x1F) << 3)};
    fwrite(px, 1, 3, f);
  }
  fclose(f);
}

int main(int argc, char **argv) {
  static uint16_t base[olmec::W * olmec::H], fb[olmec::W * olmec::H];
  static uint16_t jawTile[olmec::JAW_TILE_W * olmec::JAW_TILE_H];
  if (argc > 2 && strcmp(argv[1], "--menu") == 0) {
    olmec::renderMenu(base);
    memcpy(fb, base, sizeof(fb));
    if (argc > 3) {
      int wedge = atoi(argv[3]);
      float amt = argc > 4 ? atof(argv[4]) : 0.6f;
      if (wedge >= 0 && wedge < olmec::MENU_WEDGES) olmec::menuWedgeGlow(fb, base, wedge, amt);
    }
    writeRgb(argv[2], fb);
    return 0;
  }
  int scene = argc > 13 ? atoi(argv[13]) : olmec::SCENE_MOSS;
  olmec::renderBase(base, scene);
  olmec::renderJawTile(jawTile, scene);
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
  writeRgb(argv[1], fb);
  return 0;
}
