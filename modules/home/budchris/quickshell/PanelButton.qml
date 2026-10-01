import QtQuick

Rectangle {
    id: root

    property string label: ""
    property bool active: false
    property color backgroundColor: "transparent"
    property color activeColor: "#33467c"
    property color foregroundColor: "#c0caf5"
    property color hoverColor: "#414868"
    signal clicked(int button)
    signal wheelMoved(int delta)

    implicitWidth: Math.max(30, textItem.implicitWidth + 16)
    implicitHeight: 28
    radius: 6
    color: active ? activeColor : (mouse.containsMouse ? hoverColor : backgroundColor)

    Text {
        id: textItem
        anchors.centerIn: parent
        text: root.label
        color: root.foregroundColor
        font.family: "JetBrainsMono Nerd Font Mono"
        font.pixelSize: 13
    }

    MouseArea {
        id: mouse
        anchors.fill: parent
        hoverEnabled: true
        acceptedButtons: Qt.LeftButton | Qt.MiddleButton | Qt.RightButton
        onClicked: event => root.clicked(event.button)
        onWheel: event => root.wheelMoved(event.angleDelta.y)
    }
}
