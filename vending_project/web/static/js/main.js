document.addEventListener("DOMContentLoaded", function () {
    // 영수증 이미지 클릭 시 새 탭에서 원본 보기
    const previewImages = document.querySelectorAll(".preview-clickable");
    previewImages.forEach(img => {
        img.addEventListener("click", function () {
            window.open(this.src, "_blank");
        });
    });

    // 로그 테스트 전송 비동기 AJAX 처리
    const testButtons = document.querySelectorAll(".btn-test-log");
    testButtons.forEach(btn => {
        btn.addEventListener("click", async function () {
            const logType = this.getAttribute("data-log-type");
            this.disabled = true;
            this.innerText = "전송 중...";

            try {
                const res = await fetch(`/logs/test/${logType}`, { method: "POST" });
                const data = await res.json();
                if (data.success) {
                    alert("성공: " + data.message);
                } else {
                    alert("실패: 로그 채널 ID를 확인하세요.");
                }
            } catch (err) {
                alert("전송 중 네트워크 오류가 발생했습니다.");
            } finally {
                this.disabled = false;
                this.innerText = "테스트 전송";
            }
        });
    });
});