from __future__ import annotations

from PySide6.QtWidgets import QDialog, QDialogButtonBox, QDoubleSpinBox, QFormLayout, QVBoxLayout

from ankiistudio.ui.design_system.components import ASDialog
from ankiistudio.models import ProjectData


class VoicevoxSettingsDialog(ASDialog):
    def __init__(self, project: ProjectData, parent=None) -> None:
        super().__init__(parent)
        self.project = project
        self.setWindowTitle("Ajustar voz do VOICEVOX")
        self.setMinimumWidth(420)
        root = QVBoxLayout(self)
        form = QFormLayout()
        form.setHorizontalSpacing(14)
        form.setVerticalSpacing(10)

        self.speed = self._spin(0.5, 2.0, 0.05, project.voicevox_speed_scale)
        self.pitch = self._spin(-0.15, 0.15, 0.01, project.voicevox_pitch_scale, 3)
        self.intonation = self._spin(0.0, 2.0, 0.05, project.voicevox_intonation_scale)
        self.volume = self._spin(0.0, 2.0, 0.05, project.voicevox_volume_scale)
        self.pause = self._spin(0.0, 2.0, 0.05, project.voicevox_pause_length_scale)

        form.addRow("Velocidade", self.speed)
        form.addRow("Tom", self.pitch)
        form.addRow("Entonação", self.intonation)
        form.addRow("Volume", self.volume)
        form.addRow("Escala das pausas", self.pause)
        root.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.RestoreDefaults
            | QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.RestoreDefaults).clicked.connect(self.restore_defaults)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    @staticmethod
    def _spin(minimum: float, maximum: float, step: float, value: float, decimals: int = 2) -> QDoubleSpinBox:
        widget = QDoubleSpinBox()
        widget.setRange(minimum, maximum)
        widget.setSingleStep(step)
        widget.setDecimals(decimals)
        widget.setValue(value)
        return widget

    def restore_defaults(self) -> None:
        self.speed.setValue(1.0)
        self.pitch.setValue(0.0)
        self.intonation.setValue(1.0)
        self.volume.setValue(1.0)
        self.pause.setValue(1.0)

    def apply_to(self, project: ProjectData) -> None:
        project.voicevox_speed_scale = self.speed.value()
        project.voicevox_pitch_scale = self.pitch.value()
        project.voicevox_intonation_scale = self.intonation.value()
        project.voicevox_volume_scale = self.volume.value()
        project.voicevox_pause_length_scale = self.pause.value()
