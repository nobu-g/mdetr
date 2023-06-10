# How to Install MDETR

```shell
poetry install
git clone https://github.com/philferriere/cocoapi.git
```

Edit `cocoapi/PythonAPI/pycocotools/cocoeval.py` so that the third argument of `np.linspace` is integer.

```python
np.linspace(.5, 0.95, int(np.round((0.95 - .5) / .05) + 1), endpoint=True)
```

```shell
cd cocoapi/PythonAPI
python3 setup.py build_ext install
```

## Reference

https://jun-networks.hatenablog.com/entry/2019/07/11/203350
