export class Knob {
  constructor(container, { label, min, max, value, step = 0.001, onChange }) {
    this.min = min;
    this.max = max;
    this.onChange = onChange;
    this._render(container, label, min, max, value, step);
  }

  _render(container, label, min, max, value, step) {
    const wrapper = document.createElement('div');
    wrapper.className = 'knob-wrapper';

    const labelEl = document.createElement('div');
    labelEl.className = 'knob-label';
    labelEl.textContent = label;

    const input = document.createElement('input');
    input.type = 'range';
    input.className = 'knob';
    input.min = min;
    input.max = max;
    input.step = step;
    input.value = value;

    const valueEl = document.createElement('div');
    valueEl.className = 'knob-value';
    valueEl.textContent = this._format(value);

    input.addEventListener('input', () => {
      const v = parseFloat(input.value);
      valueEl.textContent = this._format(v);
      if (this.onChange) this.onChange(v);
    });

    wrapper.appendChild(labelEl);
    wrapper.appendChild(input);
    wrapper.appendChild(valueEl);
    container.appendChild(wrapper);

    this.input = input;
    this.valueEl = valueEl;
  }

  _format(v) {
    if (v >= 1000) return Math.round(v) + '';
    return parseFloat(v.toFixed(3)).toString();
  }

  setValue(v) {
    this.input.value = v;
    this.valueEl.textContent = this._format(v);
  }
}
