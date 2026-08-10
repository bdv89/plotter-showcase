/// <reference types="vite/client" />

// Bundle plotly pré-compilé — c'est celui que react-plotly.js charge en interne.
// On l'importe par ce chemin exact dans PlotView (voir le commentaire là-bas) ;
// il n'a pas de .d.ts propre, mais l'API est celle de 'plotly.js'.
declare module 'plotly.js/dist/plotly' {
  export * from 'plotly.js';
  import Plotly from 'plotly.js';
  export default Plotly;
}
