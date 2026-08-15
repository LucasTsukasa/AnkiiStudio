from __future__ import annotations

from pathlib import Path

from ankiistudio.services.audio.base import (
    AudioGenerationResult,
    AudioProvider,
    PermanentAudioProviderError,
)


class AudioProviderPool(AudioProvider):
    def __init__(
        self,
        key: str,
        providers: list[tuple],
        blocked_profiles: dict[str, str] | None = None,
        unavailable_message: str = "",
    ) -> None:
        self.key = key
        # Mantém a forma histórica (label, provider) para compatibilidade externa/testes.
        self.providers: list[tuple[str, AudioProvider]] = []
        self._profile_keys: list[str] = []
        for item in providers:
            if len(item) == 2:
                label, provider = item
                profile_key = str(label)
            else:
                profile_key, label, provider = item
            self.providers.append((str(label), provider))
            self._profile_keys.append(str(profile_key))
        self.blocked_profiles = blocked_profiles if blocked_profiles is not None else {}
        self.unavailable_message = unavailable_message.strip()

    def is_available(self) -> bool:
        return any(
            self._profile_keys[index] not in self.blocked_profiles and provider.is_available()
            for index, (_label, provider) in enumerate(self.providers)
        )

    def availability_error(self) -> str:
        if self.unavailable_message:
            return self.unavailable_message
        if not self.providers:
            return "Nenhum perfil de voz está configurado para este idioma."
        blocked = [
            self.blocked_profiles[key]
            for key in self._profile_keys
            if key in self.blocked_profiles
        ]
        if blocked and len(blocked) == len(self._profile_keys):
            return "; ".join(dict.fromkeys(blocked))
        return "Os perfis configurados estão indisponíveis; verifique a chave API e as configurações das vozes."

    def generate(self, text: str, destination_stem: Path) -> AudioGenerationResult | None:
        if not text.strip():
            return None
        if not self.providers:
            raise RuntimeError("Nenhum perfil de voz está configurado para este idioma.")

        errors: list[str] = []
        attempted = False
        for index, (label, provider) in enumerate(self.providers):
            profile_key = self._profile_keys[index]
            if profile_key in self.blocked_profiles:
                errors.append(f"{label}: {self.blocked_profiles[profile_key]}")
                continue
            if not provider.is_available():
                errors.append(f"{label}: indisponível")
                continue
            attempted = True
            try:
                result = provider.generate(text, destination_stem)
            except PermanentAudioProviderError as exc:
                message = str(exc)
                self.blocked_profiles[profile_key] = message
                errors.append(f"{label}: {message}")
                continue
            except Exception as exc:
                errors.append(f"{label}: {exc}")
                continue
            if result is not None:
                return result
            errors.append(f"{label}: não retornou áudio")

        if not attempted and not errors:
            raise RuntimeError("Nenhum perfil de voz está disponível para este idioma.")
        raise RuntimeError("; ".join(errors) if errors else "Nenhum perfil conseguiu gerar áudio.")
