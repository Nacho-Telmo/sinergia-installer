import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as QQC2
import org.kde.plasma.components as PlasmaComponents3
import org.kde.kirigami as Kirigami

Item {
    id: root
    width: 1920
    height: 1080

    readonly property color accentColor: "#2980b9"
    readonly property color dangerColor: "#c0392b"
    readonly property color cardBg: Qt.rgba(0.06, 0.08, 0.11, 0.78)
    readonly property color cardBorder: Qt.rgba(1, 1, 1, 0.14)
    readonly property color textPrimary: "#f2f5f9"
    readonly property color textSecondary: "#b0bac5"

    property int userIndex: userModel.lastIndex >= 0 ? userModel.lastIndex : 0
    property int sessionIndex: sessionModel.lastIndex >= 0 ? sessionModel.lastIndex : 0
    property string errorMessage: ""

    Image {
        id: wallpaper
        anchors.fill: parent
        source: config.background || "/usr/share/backgrounds/sinergia/sinergia2_fhd.jpg"
        fillMode: Image.PreserveAspectCrop
        asynchronous: true
        cache: true
    }

    Rectangle {
        anchors.fill: parent
        gradient: Gradient {
            GradientStop { position: 0.0; color: Qt.rgba(0.03, 0.04, 0.07, 0.42) }
            GradientStop { position: 0.5; color: Qt.rgba(0.03, 0.04, 0.07, 0.55) }
            GradientStop { position: 1.0; color: Qt.rgba(0.02, 0.03, 0.05, 0.72) }
        }
    }

    // Reloj y fecha superior
    Column {
        anchors.top: parent.top
        anchors.topMargin: 56
        anchors.horizontalCenter: parent.horizontalCenter
        spacing: 4

        Text {
            id: clockText
            anchors.horizontalCenter: parent.horizontalCenter
            color: root.textPrimary
            font.pixelSize: 54
            font.weight: Font.DemiBold
            text: Qt.formatTime(new Date(), "HH:mm")
        }

        Text {
            id: dateText
            anchors.horizontalCenter: parent.horizontalCenter
            color: root.textSecondary
            font.pixelSize: 16
            text: Qt.formatDate(new Date(), "dddd, d 'de' MMMM 'de' yyyy")
        }

        Timer {
            interval: 1000
            running: true
            repeat: true
            onTriggered: {
                var now = new Date()
                clockText.text = Qt.formatTime(now, "HH:mm")
                dateText.text = Qt.formatDate(now, "dddd, d 'de' MMMM 'de' yyyy")
            }
        }
    }

    // Tarjeta central de inicio de sesión
    Rectangle {
        id: loginCard
        width: 400
        implicitHeight: cardColumn.implicitHeight + 56
        anchors.centerIn: parent
        radius: 16
        color: root.cardBg
        border.color: root.cardBorder
        border.width: 1

        ColumnLayout {
            id: cardColumn
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: parent.top
            anchors.margins: 28
            spacing: 14

            // Emblema / Título Sinergia Linux
            Rectangle {
                Layout.alignment: Qt.AlignHCenter
                width: 72
                height: 72
                radius: 36
                color: Qt.rgba(0.16, 0.50, 0.73, 0.22)
                border.color: root.accentColor
                border.width: 2

                Image {
                    id: logoImg
                    anchors.centerIn: parent
                    width: 44
                    height: 44
                    source: "/usr/share/pixmaps/sinergia-logo.png"
                    fillMode: Image.PreserveAspectFit
                    visible: status === Image.Ready
                }

                Text {
                    anchors.centerIn: parent
                    visible: logoImg.status !== Image.Ready
                    text: "S"
                    color: root.textPrimary
                    font.pixelSize: 32
                    font.bold: true
                }
            }

            Text {
                Layout.alignment: Qt.AlignHCenter
                text: "Sinergia Linux"
                color: root.textPrimary
                font.pixelSize: 20
                font.bold: true
            }

            // Selector de usuario
            QQC2.ComboBox {
                id: userBox
                Layout.fillWidth: true
                model: userModel
                textRole: "realName"
                currentIndex: root.userIndex
                onCurrentIndexChanged: root.userIndex = currentIndex
                displayText: currentText !== "" ? currentText : (userModel.data(userModel.index(currentIndex, 0), Qt.UserRole + 1) || "Usuario")
            }

            // Campo de contraseña
            QQC2.TextField {
                id: passwordField
                Layout.fillWidth: true
                height: 42
                echoMode: TextInput.Password
                placeholderText: "Contraseña"
                color: root.textPrimary
                placeholderTextColor: root.textSecondary
                focus: true
                background: Rectangle {
                    radius: 8
                    color: Qt.rgba(1, 1, 1, 0.08)
                    border.color: passwordField.activeFocus ? root.accentColor : Qt.rgba(1, 1, 1, 0.18)
                    border.width: 1
                }
                Keys.onReturnPressed: doLogin()
                Keys.onEnterPressed: doLogin()
            }

            // Mensaje de error PAM
            Text {
                Layout.fillWidth: true
                visible: root.errorMessage !== ""
                text: root.errorMessage
                color: "#ff6b6b"
                font.pixelSize: 13
                horizontalAlignment: Text.AlignHCenter
                wrapMode: Text.WordWrap
            }

            // Botón Iniciar sesión
            QQC2.Button {
                id: loginButton
                Layout.fillWidth: true
                height: 42
                text: "Iniciar sesión"
                onClicked: doLogin()
                contentItem: Text {
                    text: loginButton.text
                    color: "#ffffff"
                    font.pixelSize: 15
                    font.bold: true
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                }
                background: Rectangle {
                    radius: 8
                    color: loginButton.pressed ? Qt.darker(root.accentColor, 1.2)
                         : loginButton.hovered ? Qt.lighter(root.accentColor, 1.12)
                         : root.accentColor
                }
            }
        }
    }

    // Barra inferior: selector de sesión (Wayland / X11) y botones de energía
    RowLayout {
        anchors.bottom: parent.bottom
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.margins: 28
        spacing: 10

        QQC2.ComboBox {
            id: sessionBox
            Layout.preferredWidth: 230
            model: sessionModel
            textRole: "name"
            currentIndex: root.sessionIndex
            onCurrentIndexChanged: root.sessionIndex = currentIndex
        }

        Item { Layout.fillWidth: true }

        QQC2.Button {
            id: suspendButton
            height: 36
            text: "Suspender"
            enabled: sddm.canSuspend
            opacity: enabled ? 1.0 : 0.45
            onClicked: sddm.suspend()
            contentItem: Text {
                text: suspendButton.text
                color: root.textPrimary
                font.pixelSize: 13
                horizontalAlignment: Text.AlignHCenter
                verticalAlignment: Text.AlignVCenter
            }
            background: Rectangle {
                radius: 8
                color: suspendButton.hovered ? Qt.rgba(1, 1, 1, 0.14) : root.cardBg
                border.color: root.cardBorder
                border.width: 1
            }
        }

        QQC2.Button {
            id: rebootButton
            height: 36
            text: "Reiniciar"
            enabled: sddm.canReboot
            opacity: enabled ? 1.0 : 0.45
            onClicked: sddm.reboot()
            contentItem: Text {
                text: rebootButton.text
                color: root.textPrimary
                font.pixelSize: 13
                horizontalAlignment: Text.AlignHCenter
                verticalAlignment: Text.AlignVCenter
            }
            background: Rectangle {
                radius: 8
                color: rebootButton.hovered ? Qt.rgba(0.16, 0.50, 0.73, 0.35) : root.cardBg
                border.color: rebootButton.hovered ? root.accentColor : root.cardBorder
                border.width: 1
            }
        }

        QQC2.Button {
            id: powerOffButton
            height: 36
            text: "Apagar"
            enabled: sddm.canPowerOff
            opacity: enabled ? 1.0 : 0.45
            onClicked: sddm.powerOff()
            contentItem: Text {
                text: powerOffButton.text
                color: "#ffffff"
                font.pixelSize: 13
                font.bold: true
                horizontalAlignment: Text.AlignHCenter
                verticalAlignment: Text.AlignVCenter
            }
            background: Rectangle {
                radius: 8
                color: powerOffButton.pressed ? Qt.darker(root.dangerColor, 1.2)
                     : powerOffButton.hovered ? root.dangerColor
                     : Qt.rgba(0.75, 0.22, 0.17, 0.55)
                border.color: Qt.rgba(1, 0.45, 0.40, 0.45)
                border.width: 1
            }
        }
    }

    function doLogin() {
        root.errorMessage = ""
        var uname = userModel.data(userModel.index(userBox.currentIndex, 0), Qt.UserRole + 1)
        if (!uname || uname === "") {
            uname = userBox.currentText
        }
        sddm.login(uname, passwordField.text, sessionBox.currentIndex)
    }

    Connections {
        target: sddm
        function onLoginFailed() {
            root.errorMessage = "Contraseña incorrecta. Intentá de nuevo."
            passwordField.text = ""
            passwordField.forceActiveFocus()
        }
        function onLoginSucceeded() {
            root.errorMessage = ""
        }
    }
}
