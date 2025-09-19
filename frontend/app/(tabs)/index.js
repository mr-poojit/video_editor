import React, { useState, useRef } from "react";
import {
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
  Image,
  Dimensions,
  Platform,
  ActivityIndicator,
} from "react-native";
import * as ImagePicker from "expo-image-picker";
import { Video } from "expo-av";
import Slider from "@react-native-community/slider";

const { width: SCREEN_WIDTH, height: SCREEN_HEIGHT } = Dimensions.get("window");
const VIDEO_BOX_HEIGHT = SCREEN_HEIGHT * 0.45;

export default function Editor() {
  const videoRef = useRef(null);
  const [video, setVideo] = useState(null);
  const [overlays, setOverlays] = useState([]);
  const [status, setStatus] = useState({});
  const [selected, setSelected] = useState(null);
  const [progress, setProgress] = useState(null);
  const [rendering, setRendering] = useState(false);
  const [outputUrl, setOutputUrl] = useState(null);

  // pick video
  const pickVideo = async () => {
    const res = await ImagePicker.launchImageLibraryAsync({
      mediaTypes: ImagePicker.MediaTypeOptions.Videos,
    });
    if (!res.canceled && res.assets?.length) {
      setVideo(res.assets[0]);
    }
  };

  // add text overlay
  const addText = () => {
    const id = Date.now().toString();
    setOverlays((o) => [
      ...o,
      {
        id,
        type: "text",
        text: "New Text",
        x: 50,
        y: 50,
        w: 120,
        h: 40,
        start: 0,
        end: 5,
        z: overlays.length,
      },
    ]);
    setSelected(id);
  };

  // add image overlay
  const addImage = async () => {
    const res = await ImagePicker.launchImageLibraryAsync({
      mediaTypes: ImagePicker.MediaTypeOptions.Images,
    });
    if (!res.canceled && res.assets?.length) {
      const id = Date.now().toString();
      setOverlays((o) => [
        ...o,
        {
          id,
          type: "image",
          uri: res.assets[0].uri,
          x: 80,
          y: 80,
          w: 100,
          h: 100,
          start: 2,
          end: 8,
          z: overlays.length,
        },
      ]);
      setSelected(id);
    }
  };

  // submit render
  const submitRender = async () => {
    if (!video) return alert("Please upload a video first!");
    setRendering(true);
    setProgress(0);

    try {
      const formData = new FormData();

      // fix file URI
      const videoUri = video.uri.startsWith("file://")
        ? video.uri
        : `file://${video.uri}`;

      formData.append("file", {
        uri: videoUri,
        name: "video.mp4",
        type: "video/mp4",
      });

      // overlays must be a string
      formData.append("overlays", JSON.stringify(overlays));

      // 👇 IMPORTANT: Use LAN IP if testing on physical device
      const API_BASE =
        Platform.OS === "android"
          ? "http://10.0.2.2:8000"
          : "http://127.0.0.1:8000";

      const res = await fetch(`${API_BASE}/upload`, {
        method: "POST",
        body: formData,
        headers: {
          Accept: "application/json",
        },
      });

      const text = await res.text();
      console.log("Upload response text:", text);

      if (!res.ok) {
        throw new Error(`Upload failed: ${res.status} - ${text}`);
      }

      const { job_id } = JSON.parse(text);
      console.log("Job ID:", job_id);
    } catch (e) {
      console.error("Submit error", e);
      setRendering(false);
    }
  };

  const currentTime =
    status?.positionMillis != null ? status.positionMillis / 1000 : 0;

  return (
    <View style={styles.root}>
      {/* controls */}
      <View style={styles.toolbar}>
        <TouchableOpacity onPress={pickVideo} style={styles.btn}>
          <Text style={styles.btnText}>Add Video</Text>
        </TouchableOpacity>
        <TouchableOpacity onPress={addText} style={styles.btn}>
          <Text style={styles.btnText}>Add Text</Text>
        </TouchableOpacity>
        <TouchableOpacity onPress={addImage} style={styles.btn}>
          <Text style={styles.btnText}>Add Image</Text>
        </TouchableOpacity>
      </View>

      {/* video container */}
      <View style={styles.videoBox}>
        {video &&
          (Platform.OS === "web" ? (
            <video
              src={video.uri}
              controls
              style={{
                width: "100%",
                height: "100%",
                objectFit: "contain",
                backgroundColor: "black",
              }}
            />
          ) : (
            <Video
              ref={videoRef}
              source={{ uri: video.uri }}
              style={{ width: "100%", height: "100%" }}
              useNativeControls
              resizeMode="contain"
              onPlaybackStatusUpdate={setStatus}
            />
          ))}

        {/* overlays */}
        {overlays.map((o) => {
          if (currentTime < o.start || currentTime > o.end) return null;
          return (
            <View
              key={o.id}
              style={[
                styles.overlay,
                {
                  top: o.y,
                  left: o.x,
                  width: o.w,
                  height: o.h,
                  borderColor: selected === o.id ? "cyan" : "transparent",
                  zIndex: o.z,
                },
              ]}
            >
              {o.type === "text" && (
                <Text style={styles.overlayText}>{o.text}</Text>
              )}
              {o.type === "image" && (
                <Image
                  source={{ uri: o.uri }}
                  style={{ width: "100%", height: "100%" }}
                  resizeMode="contain"
                />
              )}
            </View>
          );
        })}
      </View>

      {/* sliders for overlay timing */}
      {selected && (
        <View style={styles.sliderBox}>
          <Text style={styles.sliderLabel}>Start Time</Text>
          <Slider
            minimumValue={0}
            maximumValue={status?.durationMillis / 1000 || 30}
            value={overlays.find((o) => o.id === selected)?.start || 0}
            onValueChange={(v) =>
              setOverlays((os) =>
                os.map((o) =>
                  o.id === selected ? { ...o, start: Math.floor(v) } : o
                )
              )
            }
          />
          <Text style={styles.sliderLabel}>
            {Math.floor(overlays.find((o) => o.id === selected)?.start || 0)}{" "}
            sec
          </Text>

          <Text style={styles.sliderLabel}>End Time</Text>
          <Slider
            minimumValue={0}
            maximumValue={status?.durationMillis / 1000 || 30}
            value={overlays.find((o) => o.id === selected)?.end || 5}
            onValueChange={(v) =>
              setOverlays((os) =>
                os.map((o) =>
                  o.id === selected ? { ...o, end: Math.floor(v) } : o
                )
              )
            }
          />
          <Text style={styles.sliderLabel}>
            {Math.floor(overlays.find((o) => o.id === selected)?.end || 0)} sec
          </Text>
        </View>
      )}

      {/* submit button */}
      <TouchableOpacity
        onPress={submitRender}
        style={[styles.btn, { margin: 20, backgroundColor: "green" }]}
      >
        <Text style={styles.btnText}>Submit & Render</Text>
      </TouchableOpacity>

      {/* progress bar */}
      {rendering && (
        <View style={styles.progressBox}>
          <Text style={{ color: "white" }}>
            Rendering... {progress != null ? `${progress}%` : ""}
          </Text>
          <ActivityIndicator color="white" />
        </View>
      )}

      {/* final result */}
      {outputUrl && (
        <View style={{ padding: 10 }}>
          <Text style={{ color: "lightgreen" }}>✅ Render Complete!</Text>
          <Text style={{ color: "cyan" }}>Output: {outputUrl}</Text>
        </View>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: "#1a1a1a" },
  toolbar: { flexDirection: "row", padding: 10 },
  btn: {
    backgroundColor: "#0a84ff",
    padding: 10,
    borderRadius: 6,
    marginRight: 6,
  },
  btnText: { color: "white" },
  videoBox: {
    width: "100%",
    height: VIDEO_BOX_HEIGHT,
    backgroundColor: "black",
    justifyContent: "center",
    alignItems: "center",
    position: "relative",
  },
  overlay: {
    position: "absolute",
    borderWidth: 1,
  },
  overlayText: { color: "white", fontSize: 18 },
  sliderBox: { padding: 10, backgroundColor: "#222" },
  sliderLabel: { color: "white", marginVertical: 4 },
  progressBox: {
    padding: 12,
    backgroundColor: "#333",
    borderRadius: 8,
    alignItems: "center",
    margin: 10,
  },
});
