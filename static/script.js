let mediaRecorder;
let audioChunks = [];
let recordedBlob = null;

const recordBtn = document.getElementById("recordBtn");
const stopBtn = document.getElementById("stopBtn");
const recordStatus = document.getElementById("recordStatus");
const recordedAudioPlayer = document.getElementById("recordedAudioPlayer");

recordBtn.addEventListener("click", async () => {
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    const mimeTypes = [
      "audio/webm;codecs=opus",
      "audio/webm",
      "audio/ogg;codecs=opus",
      "audio/ogg"
    ];
    const supportedMime = mimeTypes.find((type) => MediaRecorder.isTypeSupported(type));
    mediaRecorder = supportedMime
      ? new MediaRecorder(stream, { mimeType: supportedMime })
      : new MediaRecorder(stream);
    audioChunks = [];

    mediaRecorder.ondataavailable = (e) => {
      if (e.data.size > 0) audioChunks.push(e.data);
    };

    mediaRecorder.onstop = () => {
      recordedBlob = new Blob(audioChunks, { type: mediaRecorder.mimeType || "audio/webm" });
      recordedAudioPlayer.src = URL.createObjectURL(recordedBlob);
      recordedAudioPlayer.classList.remove("hidden");
      stream.getTracks().forEach((t) => t.stop());
    };

    mediaRecorder.start();
    recordBtn.disabled = true;
    stopBtn.disabled = false;
    recordStatus.textContent = "Recording...";
  } catch (err) {
    alert("Couldn't access the microphone: " + err.message);
  }
});

stopBtn.addEventListener("click", () => {
  mediaRecorder.stop();
  recordBtn.disabled = false;
  stopBtn.disabled = true;
  recordStatus.textContent = "Recorded. Ready to submit.";
});

const imageInput = document.getElementById("imageInput");
const imagePreview = document.getElementById("imagePreview");
const dropzoneText = document.getElementById("dropzoneText");

imageInput.addEventListener("change", () => {
  const file = imageInput.files[0];
  if (file) {
    imagePreview.src = URL.createObjectURL(file);
    imagePreview.classList.remove("hidden");
    dropzoneText.textContent = file.name;
  }
});

const form = document.getElementById("multimodalForm");
const resultBox = document.getElementById("resultBox");
const answerText = document.getElementById("answerText");
const answerAudio = document.getElementById("answerAudio");
const submitBtn = document.getElementById("submitBtn");

form.addEventListener("submit", async (e) => {
  e.preventDefault();

  if (!imageInput.files[0]) {
    alert("Please choose an image first.");
    return;
  }

  const formData = new FormData();
  formData.append("image", imageInput.files[0]);

  if (recordedBlob) {
    const extension = recordedBlob.type.includes("ogg") ? "ogg" : "webm";
    formData.append("audio", recordedBlob, `question.${extension}`);
  }

  submitBtn.disabled = true;
  submitBtn.textContent = "Thinking...";

  try {
    const res = await fetch("/process", { method: "POST", body: formData });
    const data = await res.json();

    if (data.error) {
      alert(data.error);
    } else {
      resultBox.classList.remove("hidden");
      answerText.textContent = data.answer;
      if (data.audio_url) {
        answerAudio.src = data.audio_url;
        answerAudio.classList.remove("hidden");
      } else {
        answerAudio.classList.add("hidden");
      }
      resultBox.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  } catch (err) {
    alert("Request failed: " + err.message);
  } finally {
    submitBtn.disabled = false;
    submitBtn.textContent = "Ask";
  }
});
