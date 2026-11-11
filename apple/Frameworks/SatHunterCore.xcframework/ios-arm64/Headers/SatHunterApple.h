#ifndef SATHUNTER_APPLE_H
#define SATHUNTER_APPLE_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

bool sh_apple_init(const char *data_dir);
char *sh_apple_command(const char *json);
void sh_apple_string_free(char *value);
uint32_t sh_apple_spectrum_rows(float *output, size_t output_len,
                                double *metadata, size_t metadata_len);
size_t sh_apple_audio(float *output, size_t output_len);

#endif
