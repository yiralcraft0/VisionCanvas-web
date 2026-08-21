const getColor = [
    { id: "colwhite", color: [254, 254, 254] },
    { id: "colred", color: [255, 0, 0] },
    { id: "colgreen", color: [0, 128, 0] },
    { id: "colblue", color: [0, 0, 255] },
    { id: "colyellow", color: [252, 252, 0] },
    { id: "colviolet", color: [238, 130, 238] },
    { id: "colorange", color: [254, 164, 0] },
    { id: "colhotpink", color: [252, 104, 178] },
    { id: "colMulti" }
];

getColor.forEach(colors => {
    const selectColor = document.getElementById(colors.id);

    if (selectColor) {
        selectColor.addEventListener("mousedown", () => {

            if (colors.id == "colMulti") {
                selectColor.addEventListener("change", () => {
                    fetch(`${window.origin}/setColor`, {
                        method: "POST",
                        headers: {
                            "Content-Type": "application/json"
                        },
                        body: JSON.stringify({
                            color: selectColor.value
                        })
                    });
                    console.log("featch done");
                }, 1);

            } else {
                fetch("/setColor", {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json"
                    },
                    body: JSON.stringify({
                        color: colors.color
                    })
                });
            };
        });
    }
    console.log("featch done");
});

const sizeMinus = document.getElementById("sizeMinus")
const sizePlus = document.getElementById("sizePlus")
const brushSizeBox = document.getElementById("brushSizeBox")


sizeMinus.addEventListener("click", () => {
    if (brushSizeBox.value > 1) {
        var brushSize = brushSizeBox.value;
        brushSizeBox.value--;
        brushSize = brushSizeBox.value

        fetch(`${window.origin}/setBrushSize`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                size: brushSize
            })

        });
    };

});

sizePlus.addEventListener("click", () => {

    if (brushSizeBox.value < 20) {
        var brushSize = brushSizeBox.value;
        brushSizeBox.value++;
        brushSize = brushSizeBox.value

        fetch(`${window.origin}/setBrushSize`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                size: String(brushSize)
            })

        });
    };
});

brushSizeBox.addEventListener("change", () => {
    if (brushSizeBox.value > 20) {
        brushSizeBox.value = 20;
    } else if (brushSizeBox.value < 1) {
        brushSizeBox.value = 1;
    };

    var brushSize = brushSizeBox.value
    fetch(`${window.origin}/setBrushSize`, {
        method: "POST",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify({
            size: String(brushSize)
        })

    });
});


