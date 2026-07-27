from __future__ import annotations


def build_stylesheet() -> str:
    return """
        QWidget {
            color: #202124;
            font-family: "Microsoft YaHei";
            font-size: 14px;
        }

        QMainWindow,
        QTabWidget::pane {
            background: #f5f7fb;
        }

        QTabBar::tab {
            min-width: 108px;
            padding: 10px 12px;
        }

        QTabBar::tab:selected {
            background: #ffffff;
            font-weight: 600;
        }

        QGroupBox {
            background: #ffffff;
            border: 1px solid #dfe3eb;
            border-radius: 6px;
            font-weight: 600;
            margin-top: 12px;
            padding-top: 16px;
        }

        QGroupBox::title {
            left: 12px;
            padding: 0 4px;
        }

        QFrame#metricCard,
        QFrame#noticeFrame {
            background: #ffffff;
            border: 1px solid #dfe3eb;
            border-radius: 6px;
        }

        QLabel#metricTitle,
        QLabel#summaryLabel,
        QLabel#hintLabel {
            color: #5f6368;
            font-size: 13px;
            font-weight: 500;
        }

        QLabel#metricValue {
            color: #0f172a;
            font-size: 22px;
            font-weight: 700;
        }

        QLabel#metricDetail,
        QLabel#summaryValue,
        QLabel#noticeText {
            color: #3c4043;
            font-weight: 400;
        }

        QLabel#fieldLabel {
            font-weight: 600;
        }

        QLabel#statusPending {
            color: #92400e;
            font-weight: 600;
        }

        QLabel#disclaimerLabel {
            color: #7c2d12;
            font-size: 12px;
            font-weight: 600;
        }

        QPushButton {
            background: #1f6feb;
            border: 0;
            border-radius: 5px;
            color: #ffffff;
            font-weight: 600;
            padding: 8px 14px;
        }

        QPushButton:hover {
            background: #1557ba;
        }

        QPushButton:disabled {
            background: #aeb8c6;
            color: #f8fafc;
        }

        QLineEdit,
        QComboBox,
        QSpinBox,
        QDoubleSpinBox {
            background: #ffffff;
            border: 1px solid #cfd6e4;
            border-radius: 5px;
            padding: 6px 8px;
        }

        QTableWidget {
            background: #ffffff;
            gridline-color: #edf0f5;
            selection-background-color: #dbeafe;
            selection-color: #0f172a;
        }

        QHeaderView::section {
            background: #eef2f7;
            border: 0;
            border-right: 1px solid #dfe3eb;
            color: #202124;
            font-weight: 600;
            padding: 8px;
        }
    """
