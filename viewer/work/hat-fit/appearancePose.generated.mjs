/** glTF marks only skin joints as Bones. Unweighted ancestors may be Object3Ds. */
export function appearancePosePairs(scene, bones) {
    var pairs = [];
    scene.traverse(function (object) {
        var source = bones.get(object.name);
        if (source)
            pairs.push([object, source]);
    });
    return pairs;
}
export function syncAppearancePose(scene, body, pairs) {
    scene.position.copy(body.position);
    scene.quaternion.copy(body.quaternion);
    scene.scale.copy(body.scale);
    for (var _i = 0, pairs_1 = pairs; _i < pairs_1.length; _i++) {
        var _a = pairs_1[_i], target = _a[0], source = _a[1];
        target.position.copy(source.position);
        target.quaternion.copy(source.quaternion);
        target.scale.copy(source.scale);
    }
    scene.updateMatrixWorld(true);
}
