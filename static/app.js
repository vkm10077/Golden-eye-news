let selectedCategory = "all";
let refreshSeconds = 60;
let audioAlertsEnabled = false;

const notifiedNews = new Set();


function formatNewsTime(dateValue) {
    const date = new Date(dateValue);

    if (isNaN(date.getTime())) {
        return "अभी";
    }

    return new Intl.DateTimeFormat(
        "hi-IN",
        {
            hour: "2-digit",
            minute: "2-digit",
            day: "2-digit",
            month: "short"
        }
    ).format(date);
}


function enableNotifications() {
    if (!("Notification" in window)) {
        alert("इस browser में notification support नहीं है।");
        return;
    }

    Notification.requestPermission().then(permission => {

        const button = document.getElementById(
            "notificationButton"
        );

        if (permission === "granted") {
            button.innerText = "✅ Notifications Enabled";
        } else {
            button.innerText = "🔔 Enable Notifications";
        }

    });
}


function enableAudioAlerts() {
    audioAlertsEnabled = true;

    localStorage.setItem(
        "goldenEyeAudio",
        "enabled"
    );

    document.getElementById(
        "audioButton"
    ).innerText = "✅ Audio Alerts Enabled";

    playAlertSound();

    speakNews(
        "गोल्डन आई ऑडियो अलर्ट सक्रिय है।"
    );
}


function playAlertSound() {
    const AudioContext =
        window.AudioContext ||
        window.webkitAudioContext;

    if (!AudioContext) {
        return;
    }

    const context = new AudioContext();
    const oscillator = context.createOscillator();
    const gain = context.createGain();

    oscillator.connect(gain);
    gain.connect(context.destination);

    oscillator.frequency.value = 850;

    gain.gain.setValueAtTime(
        0.18,
        context.currentTime
    );

    gain.gain.exponentialRampToValueAtTime(
        0.001,
        context.currentTime + 0.7
    );

    oscillator.start();

    oscillator.stop(
        context.currentTime + 0.7
    );
}


function speakNews(text) {
    if (!("speechSynthesis" in window)) {
        alert("इस browser में Hindi voice उपलब्ध नहीं है।");
        return;
    }

    window.speechSynthesis.cancel();

    const speech = new SpeechSynthesisUtterance(text);

    speech.lang = "hi-IN";
    speech.rate = 0.92;
    speech.pitch = 1;

    const voices =
        window.speechSynthesis.getVoices();

    const hindiVoice = voices.find(
        voice =>
            voice.lang &&
            voice.lang.toLowerCase().includes("hi")
    );

    if (hindiVoice) {
        speech.voice = hindiVoice;
    }

    window.speechSynthesis.speak(speech);
}


function testAlert() {
    playAlertSound();

    if (
        document.getElementById("hindiVoice").checked
    ) {
        speakNews(
            "टेस्ट अलर्ट। गोल्डन आई समाचार प्रणाली सही काम कर रही है।"
        );
    }

    if (
        "Notification" in window &&
        Notification.permission === "granted"
    ) {
        new Notification(
            "Golden Eye Test Alert",
            {
                body: "Notification system is working."
            }
        );
    }
}


function showImportantNotification(newsItems) {
    const criticalOnly =
        document.getElementById(
            "criticalOnly"
        ).checked;

    newsItems.forEach(news => {

        if (notifiedNews.has(news.id)) {
            return;
        }

        if (
            criticalOnly &&
            news.priority !== "critical"
        ) {
            return;
        }

        if (
            news.priority !== "critical" &&
            news.priority !== "high"
        ) {
            return;
        }

        if (
            "Notification" in window &&
            Notification.permission === "granted"
        ) {
            new Notification(
                `Golden Eye: ${news.priority.toUpperCase()}`,
                {
                    body: news.title,
                    tag: news.id
                }
            );
        }

        if (audioAlertsEnabled) {
            playAlertSound();

            if (
                document.getElementById(
                    "hindiVoice"
                ).checked
            ) {
                speakNews(
                    `महत्वपूर्ण खबर। ${news.title}`
                );
            }
        }

        notifiedNews.add(news.id);

    });
}


function createNewsCard(news) {
    const template = document.getElementById(
        "newsCardTemplate"
    );

    const card =
        template.content.cloneNode(true);

    const priority =
        card.querySelector(".priority");

    priority.innerText =
        news.priority.toUpperCase();

    priority.classList.add(
        news.priority
    );

    card.querySelector(
        ".news-time"
    ).innerText = formatNewsTime(
        news.published
    );

    card.querySelector(
        ".headline"
    ).innerText = news.title;

    card.querySelector(
        ".summary"
    ).innerText = news.summary;

    card.querySelector(
        ".impact"
    ).innerText =
        `Impact: ${news.impact}`;

    card.querySelector(
        ".sentiment"
    ).innerText =
        `Sentiment: ${news.sentiment}`;

    card.querySelector(
        ".source"
    ).innerText =
        `Source: ${news.source}`;

    const affectedList =
        card.querySelector(
            ".affected-list"
        );

    if (news.affected) {
        news.affected.forEach(item => {

            const tag =
                document.createElement("span");

            tag.innerText = item;

            affectedList.appendChild(tag);

        });
    }

    card.querySelector(
        ".listen-button"
    ).onclick = function () {

        speakNews(
            `महत्वपूर्ण खबर। ${news.title}. ${news.summary}`
        );

    };

    const detailsButton =
        card.querySelector(
            ".details-button"
        );

    if (news.link) {
        detailsButton.href = news.link;
    } else {
        detailsButton.removeAttribute("href");
        detailsButton.innerText =
            "Link unavailable";
    }

    return card;
}


function renderNews(newsItems) {
    const container =
        document.getElementById(
            "newsContainer"
        );

    container.innerHTML = "";

    if (!newsItems.length) {
        container.innerHTML = `
            <div class="empty-message">
                इस category में अभी कोई खबर नहीं मिली।
            </div>
        `;

        return;
    }

    newsItems.forEach(news => {
        container.appendChild(
            createNewsCard(news)
        );
    });
}


function updateBreakingNews(newsItems) {
    if (!newsItems.length) {
        return;
    }

    const topNews = newsItems[0];

    document.getElementById(
        "breakingHeadline"
    ).innerText = topNews.title;

    document.getElementById(
        "breakingSummary"
    ).innerText = topNews.summary;
}


async function loadNews() {
    const statusText =
        document.getElementById(
            "statusText"
        );

    const refreshButton =
        document.getElementById(
            "refreshButton"
        );

    statusText.innerText =
        "Latest news loading...";

    refreshButton.disabled = true;

    try {
        const response = await fetch(
            `/api/news?category=${selectedCategory}&limit=80`,
            {
                cache: "no-store"
            }
        );

        if (!response.ok) {
            throw new Error(
                `HTTP Error ${response.status}`
            );
        }

        const result =
            await response.json();

        const newsItems =
            result.news || [];

        renderNews(newsItems);

        updateBreakingNews(newsItems);

        showImportantNotification(newsItems);

        statusText.innerText =
            `${newsItems.length} important news`;

        refreshSeconds = 60;

    } catch (error) {

        console.error(error);

        statusText.innerText =
            "News load नहीं हुई। Refresh करें।";

        document.getElementById(
            "newsContainer"
        ).innerHTML = `
            <div class="empty-message">
                News server से connection नहीं हो पाया।
            </div>
        `;

    } finally {

        refreshButton.disabled = false;

    }
}


document
    .querySelectorAll(".category")
    .forEach(button => {

        button.addEventListener(
            "click",
            function () {

                document
                    .querySelectorAll(".category")
                    .forEach(item => {
                        item.classList.remove(
                            "active"
                        );
                    });

                button.classList.add(
                    "active"
                );

                selectedCategory =
                    button.dataset.category;

                refreshSeconds = 60;

                loadNews();

            }
        );

    });


setInterval(function () {
    const autoRefresh =
        document.getElementById(
            "autoRefresh"
        );

    if (!autoRefresh.checked) {
        document.getElementById(
            "countdownText"
        ).innerText =
            "Auto refresh off";

        return;
    }

    refreshSeconds -= 1;

    document.getElementById(
        "countdownText"
    ).innerText =
        `Refresh in ${refreshSeconds}s`;

    if (refreshSeconds <= 0) {
        refreshSeconds = 60;
        loadNews();
    }

}, 1000);


if (
    localStorage.getItem(
        "goldenEyeAudio"
    ) === "enabled"
) {
    audioAlertsEnabled = true;

    document.getElementById(
        "audioButton"
    ).innerText =
        "✅ Audio Alerts Enabled";
}


if (
    "Notification" in window &&
    Notification.permission === "granted"
) {
    document.getElementById(
        "notificationButton"
    ).innerText =
        "✅ Notifications Enabled";
}


loadNews();
