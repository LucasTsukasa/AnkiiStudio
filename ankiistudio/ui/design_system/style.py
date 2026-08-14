from __future__ import annotations

from PySide6.QtWidgets import QProxyStyle, QStyle, QWidget


class AnkiiStudioProxyStyle(QProxyStyle):
    """Ajustes pequenos e centralizados sobre o estilo nativo/Fusion do Qt.

    Mantém acessibilidade e comportamento de plataforma do Qt, evitando reimplementar
    controles inteiros apenas para obter métricas visuais consistentes.
    """

    def pixelMetric(self, metric: QStyle.PixelMetric, option=None, widget: QWidget | None = None) -> int:  # type: ignore[override]
        if metric == QStyle.PixelMetric.PM_ScrollBarExtent:
            return 10
        if metric == QStyle.PixelMetric.PM_DefaultFrameWidth:
            return 1
        if metric == QStyle.PixelMetric.PM_ButtonIconSize:
            return 18
        return super().pixelMetric(metric, option, widget)
