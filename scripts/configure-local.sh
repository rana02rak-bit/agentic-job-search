#!/usr/bin/env bash
set -euo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
env_file="${project_dir}/.env"
example_file="${project_dir}/.env.example"

if [[ ! -f "${env_file}" ]]; then
  cp "${example_file}" "${env_file}"
fi

read -r -s -p "Fresh Gemini API key: " gemini_key
printf "\n"
read -r -s -p "Fresh ConnectSafely API key: " connectsafely_key
printf "\n"

temp_file="$(mktemp)"
gemini_written=0
connectsafely_written=0
while IFS= read -r line || [[ -n "${line}" ]]; do
  case "${line}" in
    GEMINI_API_KEY=*)
      printf "GEMINI_API_KEY=%s\n" "${gemini_key}" >> "${temp_file}"
      gemini_written=1
      ;;
    CONNECTSAFELY_API_KEY=*)
      printf "CONNECTSAFELY_API_KEY=%s\n" "${connectsafely_key}" >> "${temp_file}"
      connectsafely_written=1
      ;;
    OPENAI_API_KEY=*|OPENAI_MODEL=*|LINKEDIN_SEND_MODE=*)
      ;;
    *)
      printf "%s\n" "${line}" >> "${temp_file}"
      ;;
  esac
done < "${env_file}"

if [[ "${gemini_written}" -eq 0 ]]; then
  printf "GEMINI_API_KEY=%s\n" "${gemini_key}" >> "${temp_file}"
fi
if [[ "${connectsafely_written}" -eq 0 ]]; then
  printf "CONNECTSAFELY_API_KEY=%s\n" "${connectsafely_key}" >> "${temp_file}"
fi

mv "${temp_file}" "${env_file}"
chmod 600 "${env_file}"
unset gemini_key connectsafely_key

printf "Saved secrets to %s with owner-only permissions.\n" "${env_file}"
printf "Next: docker compose up --build\n"
