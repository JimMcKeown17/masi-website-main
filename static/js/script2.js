document.addEventListener('DOMContentLoaded', function () {
  particlesJS('particles-js', {
    particles: {
      number: {
        value: 0, // Start with 0 particles
        density: {
          enable: true,
          value_area: 800,
        },
      },
      shape: {
        type: 'image',
        image: {
          src: 'https://upload.wikimedia.org/wikipedia/commons/thumb/6/65/Book_icon.svg/1024px-Book_icon.svg.png', // Use a valid book SVG
          width: 100,
          height: 100,
        },
      },
      size: {
        value: 20,
      },
      move: {
        enable: true,
        speed: 3,
        random: true,
        straight: false,
        out_mode: 'bounce',
      },
      line_linked: {
        enable: false,
      },
    },
    interactivity: {
      events: {
        onclick: {
          enable: true,
          mode: 'push',
        },
      },
      modes: {
        push: {
          particles_nb: 10,
        },
      },
    },
  });

  console.log('Particles initialized with 0 particles, waiting for clicks.');
});
