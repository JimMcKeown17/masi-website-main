// Function to add scroll animation class when section is in view
function handleScroll() {
  const section = document.querySelector('.fade-in-section');
  const sectionTop = section.getBoundingClientRect().top;
  const screenBottom = window.innerHeight;

  if (sectionTop < screenBottom) {
    section.classList.add('scroll-visible');
  }
}

// Listen for scroll event
window.addEventListener('scroll', handleScroll);
