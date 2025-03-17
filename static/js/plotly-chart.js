function renderPlotlyChart() {
  // Data arrays
  var years = [
    2014, 2015, 2016, 2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024,
  ];
  var values = [12, 28, 52, 80, 122, 172, 219, 309, 548, 839, 1318];

  // Define the trace
  var trace = {
    x: years,
    y: values,
    mode: 'lines',
    name: 'Cumulative Jobs Created for Unique Community Members',
    line: {
      color: 'darkred',
      width: 3,
    },
    fill: 'tozeroy',
    fillcolor: 'rgba(178,34,34,0.3)',
  };

  // Define the data array
  var data = [trace];

  // Define the layout
  var layout = {
    paper_bgcolor: 'rgba(0,0,0,0)',
    plot_bgcolor: 'rgba(0,0,0,0)',
    xaxis: {
      title: 'Year',
      showgrid: false,
      zeroline: false,
      color: 'black',
    },
    yaxis: {
      title: 'Unique Community Members',
      showgrid: false,
      zeroline: false,
      color: 'black',
    },
    margin: {
      l: 50,
      r: 20,
      t: 20,
      b: 50,
    },
  };

  // Render the chart
  Plotly.newPlot('youth-jobs-chart', data, layout, {
    displayModeBar: false,
    responsive: true,
  });
}

// Call the function to render the chart
renderPlotlyChart();
