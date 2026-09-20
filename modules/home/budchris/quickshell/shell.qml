import QtQuick
import QtQuick.Layouts
import Quickshell
import Quickshell.Hyprland
import Quickshell.Io
import Quickshell.Services.Notifications
import Quickshell.Services.Pipewire
import Quickshell.Services.SystemTray
import Quickshell.Services.UPower
import Quickshell.Widgets

ShellRoot {
    id: root

    property bool dark: themeMode.text().trim() !== "light"
    property color background: dark ? "#1a1b26" : "#e1e2e7"
    property color foreground: dark ? "#c0caf5" : "#3760bf"
    property color muted: dark ? "#a9b1d6" : "#6172b0"
    property color surface: dark ? "#24283b" : "#d5d6db"
    property color selection: dark ? "#33467c" : "#b6bfe2"
    property color accent: dark ? "#7aa2f7" : "#2e7de9"
    property color warning: dark ? "#ff9e64" : "#b15c00"

    property string drawerPage: ""
    property real cpuPercent: 0
    property real memoryPercent: 0
    property real diskPercent: 0
    property string kernelVersion: "unknown"
    property double memoryUsed: 0
    property double memoryTotal: 0
    property double diskUsed: 0
    property double diskTotal: 0
    property double previousCpuTotal: 0
    property double previousCpuIdle: 0
    property var toastNotification: null
    property bool toastVisible: false
    property int unreadNotifications: 0
    property bool doNotDisturb: false

    function toggleDrawer(page) {
        drawerPage = drawerPage === page ? "" : page;
        if (page === "notifications" && drawerPage === page)
            unreadNotifications = 0;
    }

    function switchWorkspace(workspace) {
        if (Hyprland.usingLua)
            Hyprland.dispatch("hl.dsp.focus({ workspace = " + workspace + " })");
        else
            Hyprland.dispatch("workspace " + workspace);
    }

    function workspaceOccupied(workspace) {
        const values = Hyprland.workspaces.values;
        for (let i = 0; i < values.length; i++) {
            if (values[i].id === workspace)
                return values[i].toplevels.values.length > 0;
        }
        return false;
    }

    function bytes(value) {
        if (!value || value < 1)
            return "0 B";
        const units = ["B", "KiB", "MiB", "GiB", "TiB"];
        const index = Math.min(units.length - 1, Math.floor(Math.log(value) / Math.log(1024)));
        return (value / Math.pow(1024, index)).toFixed(index > 2 ? 1 : 0) + " " + units[index];
    }

    function volumeLabel() {
        const sink = Pipewire.defaultAudioSink;
        if (!sink || !sink.audio)
            return "VOL --";
        return sink.audio.muted ? "VOL muted" : "VOL " + Math.round(sink.audio.volume * 100) + "%";
    }

    FileView {
        id: themeMode
        path: Quickshell.env("HOME") + "/.cache/tokyo-night/mode"
        preload: true
        watchChanges: true
        printErrors: false
    }

    SystemClock {
        id: clock
        precision: SystemClock.Seconds
    }

    PwObjectTracker {
        objects: [Pipewire.defaultAudioSink]
    }

    Process {
        // Recover AppIndicator clients that were started before Quickshell's
        // StatusNotifierWatcher became available.
        command: ["quickshell-register-tray-items"]
        running: true
    }

    Process {
        id: statsProcess
        command: ["quickshell-system-stats"]
        stdout: StdioCollector {
            id: statsOutput
            waitForEnd: true
        }
        onExited: (exitCode, exitStatus) => {
            if (exitCode !== 0)
                return;
            const fields = statsOutput.text.trim().split("\t");
            if (fields.length < 7)
                return;
            const total = Number(fields[0]);
            const idle = Number(fields[1]);
            if (root.previousCpuTotal > 0 && total > root.previousCpuTotal) {
                const totalDelta = total - root.previousCpuTotal;
                const idleDelta = idle - root.previousCpuIdle;
                root.cpuPercent = Math.max(0, Math.min(100, 100 * (totalDelta - idleDelta) / totalDelta));
            }
            root.previousCpuTotal = total;
            root.previousCpuIdle = idle;
            root.memoryTotal = Number(fields[2]);
            root.memoryUsed = root.memoryTotal - Number(fields[3]);
            root.memoryPercent = root.memoryTotal ? 100 * root.memoryUsed / root.memoryTotal : 0;
            root.diskTotal = Number(fields[4]);
            root.diskUsed = Number(fields[5]);
            root.diskPercent = root.diskTotal ? 100 * root.diskUsed / root.diskTotal : 0;
            root.kernelVersion = fields[6];
        }
    }

    Timer {
        interval: 5000
        repeat: true
        running: true
        triggeredOnStart: true
        onTriggered: {
            if (!statsProcess.running)
                statsProcess.running = true;
        }
    }

    NotificationServer {
        id: notificationServer
        keepOnReload: true
        persistenceSupported: true
        bodySupported: true
        bodyMarkupSupported: false
        actionsSupported: true
        imageSupported: true
        onNotification: notification => {
            notification.tracked = true;
            root.unreadNotifications++;
            if (!root.doNotDisturb) {
                root.toastNotification = notification;
                root.toastVisible = true;
                toastTimer.restart();
            }
        }
    }

    Timer {
        id: toastTimer
        interval: 5000
        onTriggered: root.toastVisible = false
    }

    Variants {
        model: Quickshell.screens

        delegate: PanelWindow {
            id: panel
            required property ShellScreen modelData
            property bool primary: Quickshell.screens.length > 0 && modelData.name === Quickshell.screens[0].name

            screen: modelData
            anchors { top: true; left: true; right: true }
            implicitHeight: 36
            color: root.background
            exclusiveZone: 36

            Rectangle {
                anchors.fill: parent
                color: root.background
                border.color: root.surface
                border.width: 1

                Row {
                    anchors.left: parent.left
                    anchors.leftMargin: 8
                    anchors.verticalCenter: parent.verticalCenter
                    spacing: 4

                    Repeater {
                        model: 5
                        PanelButton {
                            required property int index
                            property int workspaceNumber: index + 1
                            label: workspaceNumber.toString()
                            active: Hyprland.focusedWorkspace && Hyprland.focusedWorkspace.id === workspaceNumber
                            backgroundColor: root.workspaceOccupied(workspaceNumber) ? root.surface : "transparent"
                            activeColor: root.selection
                            foregroundColor: active ? root.accent : root.foreground
                            hoverColor: root.selection
                            onClicked: button => root.switchWorkspace(workspaceNumber)
                        }
                    }
                }

                PanelButton {
                    anchors.centerIn: parent
                    label: Qt.formatDateTime(clock.date, "yyyy-MM-dd  HH:mm:ss")
                    backgroundColor: "transparent"
                    activeColor: root.selection
                    foregroundColor: root.foreground
                    hoverColor: root.surface
                    active: root.drawerPage === "clock"
                    onClicked: button => root.toggleDrawer("clock")
                }

                Row {
                    anchors.right: parent.right
                    anchors.rightMargin: 8
                    anchors.verticalCenter: parent.verticalCenter
                    spacing: 4

                    Row {
                        visible: panel.primary
                        spacing: 3

                        Repeater {
                            model: SystemTray.items
                            Item {
                                id: trayItem
                                required property var modelData
                                width: 26
                                height: 28

                                IconImage {
                                    anchors.centerIn: parent
                                    implicitWidth: 20
                                    implicitHeight: 20
                                    source: trayItem.modelData.icon
                                }

                                QsMenuAnchor {
                                    id: trayMenu
                                    menu: trayItem.modelData.menu
                                    anchor.window: panel
                                    anchor.item: trayItem
                                }

                                MouseArea {
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    acceptedButtons: Qt.LeftButton | Qt.MiddleButton | Qt.RightButton
                                    onClicked: event => {
                                        if (event.button === Qt.RightButton && trayItem.modelData.hasMenu)
                                            trayMenu.open();
                                        else if (event.button === Qt.MiddleButton)
                                            trayItem.modelData.secondaryActivate();
                                        else
                                            trayItem.modelData.activate();
                                    }
                                    onWheel: event => trayItem.modelData.scroll(event.angleDelta.y, false)
                                }
                            }
                        }
                    }

                    PanelButton {
                        label: "CPU " + root.cpuPercent.toFixed(0) + "%  MEM " + root.memoryPercent.toFixed(0) + "%  DISK " + root.diskPercent.toFixed(0) + "%"
                        backgroundColor: "transparent"
                        activeColor: root.selection
                        foregroundColor: root.foreground
                        hoverColor: root.surface
                        active: root.drawerPage === "stats"
                        onClicked: button => root.toggleDrawer("stats")
                    }

                    PanelButton {
                        label: root.volumeLabel()
                        backgroundColor: "transparent"
                        activeColor: root.selection
                        foregroundColor: Pipewire.defaultAudioSink && Pipewire.defaultAudioSink.audio && Pipewire.defaultAudioSink.audio.muted ? root.warning : root.foreground
                        hoverColor: root.surface
                        onClicked: button => {
                            const sink = Pipewire.defaultAudioSink;
                            if (button === Qt.MiddleButton && sink && sink.audio)
                                sink.audio.muted = !sink.audio.muted;
                            else
                                Quickshell.execDetached(["pavucontrol"]);
                        }
                        onWheelMoved: delta => {
                            const sink = Pipewire.defaultAudioSink;
                            if (sink && sink.audio)
                                sink.audio.volume = Math.max(0, Math.min(1.5, sink.audio.volume + (delta > 0 ? 0.05 : -0.05)));
                        }
                    }

                    PanelButton {
                        visible: UPower.displayDevice && UPower.displayDevice.isPresent && UPower.displayDevice.isLaptopBattery
                        label: "BAT " + Math.round(UPower.displayDevice.percentage) + "%"
                        backgroundColor: "transparent"
                        activeColor: root.selection
                        foregroundColor: UPower.displayDevice && UPower.displayDevice.percentage < 20 ? root.warning : root.foreground
                        hoverColor: root.surface
                        active: root.drawerPage === "battery"
                        onClicked: button => root.toggleDrawer("battery")
                    }

                    PanelButton {
                        label: root.doNotDisturb ? "DND" : (root.unreadNotifications ? "󰂚 " + root.unreadNotifications : "󰂚")
                        backgroundColor: "transparent"
                        activeColor: root.selection
                        foregroundColor: root.unreadNotifications ? root.accent : root.foreground
                        hoverColor: root.surface
                        active: root.drawerPage === "notifications"
                        onClicked: button => {
                            if (button === Qt.RightButton)
                                root.doNotDisturb = !root.doNotDisturb;
                            else
                                root.toggleDrawer("notifications");
                        }
                    }
                }
            }
        }
    }

    PanelWindow {
        id: drawer
        visible: root.drawerPage !== "" && Quickshell.screens.length > 0
        screen: Quickshell.screens.length > 0 ? Quickshell.screens[0] : null
        anchors { top: true; right: true }
        margins { top: 42; right: 8 }
        implicitWidth: 430
        implicitHeight: 440
        exclusionMode: ExclusionMode.Ignore
        color: "transparent"

        Rectangle {
            anchors.fill: parent
            radius: 10
            color: root.background
            border.color: root.selection
            border.width: 1

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 14
                spacing: 10

                RowLayout {
                    Layout.fillWidth: true
                    Text {
                        Layout.fillWidth: true
                        text: root.drawerPage === "notifications" ? "Notifications" :
                              root.drawerPage === "stats" ? "System statistics" :
                              root.drawerPage === "battery" ? "Battery" : "Date and time"
                        color: root.accent
                        font.family: "JetBrainsMono Nerd Font Mono"
                        font.pixelSize: 18
                        font.bold: true
                    }
                    PanelButton {
                        label: "×"
                        foregroundColor: root.foreground
                        hoverColor: root.selection
                        onClicked: button => root.drawerPage = ""
                    }
                }

                ColumnLayout {
                    visible: root.drawerPage === "clock"
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    Text {
                        Layout.alignment: Qt.AlignHCenter
                        text: Qt.formatDateTime(clock.date, "HH:mm:ss")
                        color: root.foreground
                        font.pixelSize: 46
                        font.family: "JetBrainsMono Nerd Font Mono"
                    }
                    Text {
                        Layout.alignment: Qt.AlignHCenter
                        text: Qt.formatDateTime(clock.date, "dddd, MMMM d, yyyy")
                        color: root.muted
                        font.pixelSize: 18
                    }
                    Item { Layout.fillHeight: true }
                }

                ColumnLayout {
                    visible: root.drawerPage === "stats"
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    spacing: 14
                    Text { text: "Kernel  " + root.kernelVersion; color: root.foreground; font.pixelSize: 15 }
                    Text { text: "CPU     " + root.cpuPercent.toFixed(1) + "%"; color: root.foreground; font.pixelSize: 15 }
                    Text { text: "Memory  " + root.bytes(root.memoryUsed) + " / " + root.bytes(root.memoryTotal) + "  (" + root.memoryPercent.toFixed(1) + "%)"; color: root.foreground; font.pixelSize: 15 }
                    Text { text: "Disk /  " + root.bytes(root.diskUsed) + " / " + root.bytes(root.diskTotal) + "  (" + root.diskPercent.toFixed(1) + "%)"; color: root.foreground; font.pixelSize: 15 }
                    Text { text: "Volume  " + root.volumeLabel().replace("VOL ", ""); color: root.foreground; font.pixelSize: 15 }
                    Item { Layout.fillHeight: true }
                }

                ColumnLayout {
                    visible: root.drawerPage === "battery"
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    Text { text: UPower.displayDevice ? "Charge: " + Math.round(UPower.displayDevice.percentage) + "%" : "No battery"; color: root.foreground; font.pixelSize: 16 }
                    Text { text: UPower.displayDevice ? "Health: " + Math.round(UPower.displayDevice.healthPercentage) + "%" : ""; color: root.muted; font.pixelSize: 14 }
                    Text { text: UPower.onBattery ? "Running on battery" : "Connected to AC power"; color: root.muted; font.pixelSize: 14 }
                    Item { Layout.fillHeight: true }
                }

                ColumnLayout {
                    visible: root.drawerPage === "notifications"
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    spacing: 8

                    RowLayout {
                        Layout.fillWidth: true
                        PanelButton {
                            label: root.doNotDisturb ? "Disable DND" : "Do not disturb"
                            active: root.doNotDisturb
                            activeColor: root.selection
                            foregroundColor: root.foreground
                            hoverColor: root.selection
                            onClicked: button => root.doNotDisturb = !root.doNotDisturb
                        }
                        Item { Layout.fillWidth: true }
                        PanelButton {
                            label: "Clear all"
                            foregroundColor: root.foreground
                            hoverColor: root.selection
                            onClicked: button => {
                                const notifications = notificationServer.trackedNotifications.values.slice();
                                for (let i = 0; i < notifications.length; i++)
                                    notifications[i].dismiss();
                                root.unreadNotifications = 0;
                            }
                        }
                    }

                    Flickable {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        contentWidth: width
                        contentHeight: notificationColumn.implicitHeight
                        clip: true

                        Column {
                            id: notificationColumn
                            width: parent.width
                            spacing: 8

                            Text {
                                visible: notificationServer.trackedNotifications.values.length === 0
                                text: "No notifications"
                                color: root.muted
                                font.pixelSize: 14
                            }

                            Repeater {
                                model: notificationServer.trackedNotifications
                                Rectangle {
                                    required property var modelData
                                    width: notificationColumn.width
                                    height: notificationContent.implicitHeight + 20
                                    radius: 8
                                    color: root.surface

                                    ColumnLayout {
                                        id: notificationContent
                                        anchors.left: parent.left
                                        anchors.right: parent.right
                                        anchors.top: parent.top
                                        anchors.margins: 10
                                        spacing: 5

                                        RowLayout {
                                            Layout.fillWidth: true
                                            Text {
                                                Layout.fillWidth: true
                                                text: modelData.appName || "Notification"
                                                color: root.accent
                                                font.bold: true
                                                elide: Text.ElideRight
                                            }
                                            Text {
                                                text: "×"
                                                color: root.muted
                                                font.pixelSize: 18
                                                MouseArea { anchors.fill: parent; onClicked: modelData.dismiss() }
                                            }
                                        }
                                        Text {
                                            Layout.fillWidth: true
                                            text: modelData.summary
                                            color: root.foreground
                                            font.bold: true
                                            wrapMode: Text.Wrap
                                        }
                                        Text {
                                            Layout.fillWidth: true
                                            visible: text.length > 0
                                            text: modelData.body
                                            textFormat: Text.PlainText
                                            color: root.muted
                                            wrapMode: Text.Wrap
                                            maximumLineCount: 4
                                            elide: Text.ElideRight
                                        }
                                        RowLayout {
                                            visible: modelData.actions.length > 0
                                            Repeater {
                                                model: modelData.actions
                                                PanelButton {
                                                    required property var modelData
                                                    label: modelData.text
                                                    foregroundColor: root.foreground
                                                    hoverColor: root.selection
                                                    onClicked: button => modelData.invoke()
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }

    PanelWindow {
        visible: root.toastVisible && root.toastNotification !== null && root.drawerPage !== "notifications" && Quickshell.screens.length > 0
        screen: Quickshell.screens.length > 0 ? Quickshell.screens[0] : null
        anchors { top: true; right: true }
        margins { top: 42; right: 8 }
        implicitWidth: 380
        implicitHeight: 120
        exclusionMode: ExclusionMode.Ignore
        color: "transparent"

        Rectangle {
            anchors.fill: parent
            radius: 10
            color: root.background
            border.color: root.accent
            border.width: 1

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 12
                Text { text: root.toastNotification ? (root.toastNotification.appName || "Notification") : ""; color: root.accent; font.bold: true }
                Text { Layout.fillWidth: true; text: root.toastNotification ? root.toastNotification.summary : ""; color: root.foreground; font.bold: true; wrapMode: Text.Wrap }
                Text { Layout.fillWidth: true; text: root.toastNotification ? root.toastNotification.body : ""; textFormat: Text.PlainText; color: root.muted; wrapMode: Text.Wrap; maximumLineCount: 2; elide: Text.ElideRight }
            }

            MouseArea {
                anchors.fill: parent
                onClicked: {
                    root.toastVisible = false;
                    root.toggleDrawer("notifications");
                }
            }
        }
    }
}
