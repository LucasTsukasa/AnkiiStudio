from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
)

from ankiistudio.constants import (
    DEFAULT_ELEVEN_MODEL,
    GEMINI_TTS_MODEL_OPTIONS,
    LANGUAGE_LABELS,
)
from ankiistudio.services.audio_profile_service import AudioVoiceProfile
from ankiistudio.ui.design_system.components import ASComboBox, ASDialog, ASLineEdit
from ankiistudio.ui.widgets import SearchableComboBox


class AudioProfileDialog(ASDialog):
    def __init__(
        self,
        provider: str,
        profile: AudioVoiceProfile | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.provider = provider
        self.profile = profile
        self.setWindowTitle("Perfil de voz Gemini" if provider == "gemini" else "Perfil de voz ElevenLabs")
        self.setMinimumWidth(460)

        root = QVBoxLayout(self)
        form = QFormLayout()
        form.setHorizontalSpacing(14)
        form.setVerticalSpacing(10)

        self.language_combo = SearchableComboBox()
        self.language_combo.set_items([(label, code) for code, label in LANGUAGE_LABELS.items()], "ja")
        self.name_input = ASLineEdit()
        self.name_input.setPlaceholderText("Ex.: Japonês natural")

        if provider == "gemini":
            self.model_combo = ASComboBox()
            self.model_combo.setEditable(True)
            for model_key, label in GEMINI_TTS_MODEL_OPTIONS:
                if model_key != "auto":
                    self.model_combo.addItem(label, model_key)
            self.voice_input = ASLineEdit()
            self.voice_input.setPlaceholderText("Ex.: Kore")
            form.addRow("Idioma", self.language_combo)
            form.addRow("Nome", self.name_input)
            form.addRow("Modelo TTS", self.model_combo)
            form.addRow("Voz", self.voice_input)
        else:
            self.model_input = ASLineEdit(DEFAULT_ELEVEN_MODEL)
            self.model_input.setPlaceholderText("Ex.: eleven_multilingual_v2")
            self.voice_input = ASLineEdit()
            self.voice_input.setPlaceholderText("Voice ID da ElevenLabs")
            form.addRow("Idioma", self.language_combo)
            form.addRow("Nome", self.name_input)
            form.addRow("Modelo", self.model_input)
            form.addRow("Voice ID", self.voice_input)

            section = QLabel("Ajustes da voz")
            section.setObjectName("SectionTitle")
            form.addRow(section)
            self.stability = self._spin(0.0, 1.0, 0.01, 0.5)
            self.similarity = self._spin(0.0, 1.0, 0.01, 0.75)
            self.style = self._spin(0.0, 1.0, 0.01, 0.0)
            self.speed = self._spin(0.7, 1.2, 0.05, 1.0)
            self.speaker_boost = QCheckBox("Aumentar semelhança com a voz original")
            self.speaker_boost.setChecked(True)
            form.addRow("Estabilidade", self.stability)
            form.addRow("Similaridade", self.similarity)
            form.addRow("Estilo", self.style)
            form.addRow("Velocidade", self.speed)
            form.addRow("", self.speaker_boost)

        self.enabled_check = QCheckBox("Usar este perfil na geração")
        self.enabled_check.setChecked(True)
        form.addRow("", self.enabled_check)
        root.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

        if profile is not None:
            self._load_profile(profile)

    @staticmethod
    def _spin(minimum: float, maximum: float, step: float, value: float) -> QDoubleSpinBox:
        widget = QDoubleSpinBox()
        widget.setRange(minimum, maximum)
        widget.setSingleStep(step)
        widget.setDecimals(2)
        widget.setValue(value)
        return widget

    def _load_profile(self, profile: AudioVoiceProfile) -> None:
        index = self.language_combo.findData(profile.language)
        if index >= 0:
            self.language_combo.setCurrentIndex(index)
        self.name_input.setText(profile.name)
        self.voice_input.setText(profile.voice)
        self.enabled_check.setChecked(profile.enabled)
        if self.provider == "gemini":
            index = self.model_combo.findData(profile.model)
            if index >= 0:
                self.model_combo.setCurrentIndex(index)
            else:
                self.model_combo.setEditText(profile.model)
        else:
            self.model_input.setText(profile.model)
            self.stability.setValue(profile.stability)
            self.similarity.setValue(profile.similarity_boost)
            self.style.setValue(profile.style)
            self.speed.setValue(profile.speed)
            self.speaker_boost.setChecked(profile.speaker_boost)

    def value(self) -> AudioVoiceProfile:
        name = self.name_input.text().strip()
        voice = self.voice_input.text().strip()
        if not name:
            raise ValueError("Informe um nome para o perfil de voz.")
        if not voice:
            raise ValueError("Informe a voz/Voice ID do perfil.")
        if self.provider == "gemini":
            model = str(self.model_combo.currentData() or self.model_combo.currentText()).strip()
        else:
            model = self.model_input.text().strip()
        if not model:
            raise ValueError("Informe o modelo de síntese.")
        language = self.language_combo.currentData()
        if language is None:
            raise ValueError("Selecione um idioma da lista.")
        values: dict[str, object] = {
            "provider": self.provider,
            "language": str(language),
            "name": name,
            "model": model,
            "voice": voice,
            "enabled": self.enabled_check.isChecked(),
        }
        if self.provider == "elevenlabs":
            values.update(
                stability=self.stability.value(),
                similarity_boost=self.similarity.value(),
                style=self.style.value(),
                speed=self.speed.value(),
                speaker_boost=self.speaker_boost.isChecked(),
            )
        if self.profile is not None:
            values["id"] = self.profile.id
        return AudioVoiceProfile(**values)
