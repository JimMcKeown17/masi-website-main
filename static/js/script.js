document.addEventListener('DOMContentLoaded', function () {
  // Stat counter animation
  const counters = document.querySelectorAll('.counter');
  const speed = 200;

  const animateCounter = (counter) => {
    const target = counter.getAttribute('data-target');
    const isPercentage = target.includes('%');
    const isX = target.includes('X');
    let count = 0;

    const updateCount = () => {
      const targetNum = parseInt(target.replace('%', '').replace('X', ''));
      const increment = targetNum / speed;

      if (count < targetNum) {
        count += increment;
        if (isPercentage) {
          counter.innerText = Math.ceil(count) + '%';
        } else if (isX) {
          counter.innerText = Math.ceil(count) + 'X';
        } else {
          counter.innerText = Math.ceil(count);
        }
        setTimeout(updateCount, 10);
      } else {
        counter.innerText = target;
      }
    };

    updateCount();
  };

  const observerOptions = {
    root: null,
    rootMargin: '0px',
    threshold: 0.1,
  };

  const observer = new IntersectionObserver((entries, observer) => {
    entries.forEach((entry) => {
      if (entry.isIntersecting) {
        animateCounter(entry.target);
        observer.unobserve(entry.target);
      }
    });
  }, observerOptions);

  counters.forEach((counter) => {
    observer.observe(counter);
  });

  // Scroll-based navbar behavior
  const navbar = document.getElementById('navbar');
  const navbarDark = document.getElementById('navbar-dark');
  const navLinks = document.querySelectorAll('.nav-link'); // Select all light nav links
  const navLinksDark = document.querySelectorAll('.nav-link-dark'); // Select all dark nav links

  // Consolidated scroll-based navbar behavior
  window.addEventListener('scroll', function () {
    if (window.scrollY > 50) {
      if (navbar) {
        navbar.classList.add('scrolled');
        navLinks.forEach((link) => link.classList.remove('nav-link-white'));
      }
      if (navbarDark) {
        navbarDark.classList.add('scrolled');
        navLinksDark.forEach((link) => link.style.color = "rgb(42, 42, 42)"); // Keep dark color
      }
    } else {
      if (navbar) {
        navbar.classList.remove('scrolled');
        navLinks.forEach((link) => link.classList.add('nav-link-white'));
      }
      if (navbarDark) {
        navbarDark.classList.remove('scrolled');
        navLinksDark.forEach((link) => link.style.color = "rgb(42, 42, 42)"); // Keep dark color initially
      }
    }
  });

  // Rest of your JavaScript remains the same...

  // Floating Stats Data Drive Section
  // const stats = document.querySelectorAll('#floating-stats .stat');
  // const sectionHeight = document.getElementById('floating-stats').offsetHeight;

  // stats.forEach((stat) => {
  //   // Random horizontal position
  //   const randomLeft = Math.random() * 90; // Prevent overflow
  //   stat.style.left = randomLeft + '%';

  //   // Random font size
  //   const randomFontSize = Math.random() * 10 + 14;
  //   stat.style.fontSize = randomFontSize + 'px';

  //   // Animate upward with fade in and fade out
  //   gsap.fromTo(
  //     stat,
  //     { y: sectionHeight, opacity: 0 },
  //     {
  //       y: -200, // Increase the negative value to make them move out of view completely
  //       opacity: 1,
  //       duration: Math.random() * 10 + 10,
  //       delay: Math.random() * 5,
  //       repeat: -1,
  //       ease: 'linear',
  //       onUpdate: function () {
  //         // Calculate fading out opacity as it moves towards the top
  //         const progress = this.progress(); // Gets a value between 0 and 1
  //         stat.style.opacity = Math.max(0, 1 - progress);
  //       },
  //       onRepeat: function () {
  //         // Randomize position and duration on each repeat
  //         stat.style.left = Math.random() * 90 + '%';
  //         stat.style.fontSize = Math.random() * 10 + 14 + 'px';
  //         this.duration(Math.random() * 10 + 10);
  //       },
  //     }
  //   );
  // });

  // // -- About Us Image Track (New Code) --

  // const track = document.getElementById('image-track');

  // // Function to handle mouse down event
  // const handleOnDown = (e) => (track.dataset.mouseDownAt = e.clientX);

  // // Function to handle mouse up event
  // const handleOnUp = () => {
  //   track.dataset.mouseDownAt = '0';
  //   track.dataset.prevPercentage = track.dataset.percentage;
  // };

  // // Function to handle mouse move event
  // const handleOnMove = (e) => {
  //   if (track.dataset.mouseDownAt === '0') return;

  //   const mouseDelta = parseFloat(track.dataset.mouseDownAt) - e.clientX,
  //     maxDelta = window.innerWidth / 2;

  //   const percentage = (mouseDelta / maxDelta) * -100,
  //     nextPercentageUnconstrained =
  //       parseFloat(track.dataset.prevPercentage) + percentage,
  //     nextPercentage = Math.max(Math.min(nextPercentageUnconstrained, 0), -100);

  //   track.dataset.percentage = nextPercentage;

  //   // Animate the track to move left and right
  //   track.animate(
  //     {
  //       transform: `translate(${nextPercentage}%, -50%)`,
  //     },
  //     { duration: 1200, fill: 'forwards' }
  //   );

  //   // Animate each image within the track
  //   for (const image of track.getElementsByClassName('image')) {
  //     image.animate(
  //       {
  //         objectPosition: `${100 + nextPercentage}% center`,
  //       },
  //       { duration: 1200, fill: 'forwards' }
  //     );
  //   }
  // };

  // Handle mouse events
  // window.onmousedown = (e) => handleOnDown(e);
  // window.ontouchstart = (e) => handleOnDown(e.touches[0]);
  // window.onmouseup = (e) => handleOnUp(e);
  // window.ontouchend = (e) => handleOnUp(e.touches[0]);
  // window.onmousemove = (e) => handleOnMove(e);
  // window.ontouchmove = (e) => handleOnMove(e.touches[0]);

  // -- End of About Us Image Track --


});
