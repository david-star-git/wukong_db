const fileInput = document.getElementById("file");
const filenameEl = document.getElementById("filename");
const dropzone = document.getElementById("dropzone");

fileInput.addEventListener("change", () => {
    if (fileInput.files.length > 0) {
        filenameEl.textContent = fileInput.files[0].name;
    }
});

dropzone.addEventListener("dragover", (e) => {
    e.preventDefault();
    dropzone.classList.add("dragover");
});

dropzone.addEventListener("dragleave", () => {
    dropzone.classList.remove("dragover");
});

dropzone.addEventListener("drop", (e) => {
    e.preventDefault();
    dropzone.classList.remove("dragover");

    if (e.dataTransfer.files.length > 0) {
        fileInput.files = e.dataTransfer.files;
        filenameEl.textContent = e.dataTransfer.files[0].name;
    }
});
